# pipeline.py

import time
import logging
import argparse
import threading
import queue
from tqdm import tqdm
from threading import Semaphore, Timer
from concurrent.futures import ThreadPoolExecutor, as_completed
from database_build.config import CURRENT_PATCH, REGIONS
from database_build.riot_api import (
    fetch_league_players,
    fetch_match_ids_by_puuid,
    fetch_match_details,
    fetch_match_timeline
)
from database_build.data_parser import parse_match_data
from database_build.db import init_db, insert_match_record
import os
import pickle

logger = logging.getLogger()

def match_exists(conn, match_id):
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM match_records WHERE match_id = ?", (match_id,))
    return cursor.fetchone() is not None

class RateLimiter:
    def __init__(self, calls_per_period, period_seconds):
        self.calls_per_period = calls_per_period
        self.period_seconds = period_seconds
        self.call_times = []

    def acquire(self):
        import time
        now = time.time()
        # Remove timestamps older than the current period window
        self.call_times = [t for t in self.call_times if now - t < self.period_seconds]
        if len(self.call_times) >= self.calls_per_period:
            sleep_time = self.period_seconds - (now - self.call_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.call_times.append(time.time())

def process_match(region, match_id, short_term_limiter, long_term_limiter):
    conn = init_db()
    try:
        short_term_limiter.acquire()
        long_term_limiter.acquire()
        match_detail = fetch_match_details(region, match_id)

        short_term_limiter.acquire()
        long_term_limiter.acquire()
        timeline = fetch_match_timeline(region, match_id)
    except Exception as e:
        logger.error(f"Error fetching match details/timeline for match {match_id}: {e}")
        conn.close()
        return

    if match_detail and timeline:
        records = parse_match_data(match_detail, timeline)
        for record in records:
            record["patch_start"] = CURRENT_PATCH
            record["region"] = region
            record["match_id"] = match_id
            insert_match_record(conn, record)
    
    conn.close()

def process_region(region, routing_limiters):
    conn = init_db()
    matches_cache_file = f"matches_cache/{region}_matches.pkl"

    routing = REGIONS[region]['routing']
    short_term_limiter = routing_limiters[routing]['short']
    long_term_limiter = routing_limiters[routing]['long']

    if os.path.exists(matches_cache_file):
        logger.info(f"Found cached matches file {matches_cache_file}. Loading cached match IDs...")
        with open(matches_cache_file, "rb") as f:
            unique_match_ids = pickle.load(f)
    else:
        #Fetching player IDs
        tiers = ["GRANDMASTER"]
        puuids = []
        for tier in tiers:
            league_data = fetch_league_players(region, tier=tier)
            if league_data and 'entries' in league_data:
                puuids.extend(player['puuid'] for player in league_data['entries'] if 'puuid' in player)
        if not puuids:
            logger.info(f"No league data for region: {region}")
            conn.close()
            return
        logger.info(f"Region {region}: Fetched {len(puuids)} PUUIDs.")

        MATCHES_PER_PUUID = 5
        total_match_requests = len(puuids) * MATCHES_PER_PUUID
        logger.info(f"Region {region}: Planning to request {total_match_requests} match details ({MATCHES_PER_PUUID} per player).")

        #Fetching match IDs
        all_match_ids = []
        for puuid in tqdm(puuids, desc=f"Fetching matches for players in {region}"):
            try:
                short_term_limiter.acquire()
                long_term_limiter.acquire()
                match_ids = fetch_match_ids_by_puuid(region, puuid, CURRENT_PATCH, count=MATCHES_PER_PUUID)
                # logger.info(f"PUUID {puuid}: Retrieved {len(match_ids)} match IDs.")
                all_match_ids.extend(match_ids)
            except Exception as e:
                logger.error(f"Error fetching match IDs for puuid {puuid}: {e}")
                continue

        unique_match_ids = list(set(all_match_ids))
        logger.info(f"Region {region}: {len(unique_match_ids)} unique matches to process out of {len(all_match_ids)}.")

        # Save unique match IDs to disk
        with open(matches_cache_file, "wb") as f:
            pickle.dump(unique_match_ids, f)
        logger.info(f"Saved {len(unique_match_ids)} unique match IDs to {matches_cache_file}")

    # Load already processed match IDs
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT match_id FROM match_records")
    processed_matches = set(row[0] for row in cursor.fetchall())
    logger.info(f"Region {region}: Found {len(processed_matches)} already processed matches in database.")

    # Filter out already processed matches
    matches_to_process = [mid for mid in unique_match_ids if mid not in processed_matches]
    logger.info(f"Region {region}: {len(matches_to_process)} matches left to process after filtering.")

    for match_id in tqdm(matches_to_process, desc=f"Processing matches in {region}"):
        process_match(region, match_id, short_term_limiter, long_term_limiter)

    conn.close()
