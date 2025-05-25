# data_parser.py

EARLY_PHASE_THRESHOLD = 600000   # 10 minutes in milliseconds
MID_PHASE_THRESHOLD = 1500000    # 25 minutes in milliseconds

def parse_match_data(match_detail, timeline):
    """
    Parse match details and timeline to extract lane matchups, stats, and item purchase timelines.
    """
    match_info = match_detail.get("info", {})
    game_duration = match_info.get("gameDuration")
    if game_duration is not None and game_duration < 300:
        # Skip remakes or games that are too short to be meaningful
        return []

    participants = match_info.get("participants", [])
    
    # Build mapping from lane to list of participants (ideally two per lane)
    lane_matchups = {}
    for p in participants:
        lane = p.get("teamPosition")
        if not lane:
            continue
        lane_matchups.setdefault(lane, []).append(p)
    
    matchup_records = []
    for lane, players in lane_matchups.items():
        if len(players) == 2:
            record = {}
            p1, p2 = players
            record["lane"] = lane
            record["champion_1"] = p1.get("championName")
            record["champion_2"] = p2.get("championName")
            record["win_1"] = p1.get("win")
            record["win_2"] = p2.get("win")
            record["kda_raw_1"] = (p1.get("kills"), p1.get("deaths"), p1.get("assists"))
            record["kda_raw_2"] = (p2.get("kills"), p2.get("deaths"), p2.get("assists"))
            record["gold_1"] = p1.get("goldEarned")
            record["gold_2"] = p2.get("goldEarned")
            record["kda_1"] = p1.get("challenges", {}).get("kda")
            record["kda_2"] = p2.get("challenges", {}).get("kda")

            # Match duration
            record["match_duration"] = game_duration

            # Champion state and position
            record["champion_transform_1"] = p1.get("championTransform")
            record["champion_transform_2"] = p2.get("championTransform")
            record["individual_position_1"] = p1.get("individualPosition")
            record["individual_position_2"] = p2.get("individualPosition")

            # Team side
            record["team_id_1"] = p1.get("teamId")
            record["team_id_2"] = p2.get("teamId")

            # Ally and enemy champions for p1
            team_id_1 = p1.get("teamId")
            participant_id_1 = p1.get("participantId")
            ally_champions_1 = [p.get("championName") for p in participants if p.get("teamId") == team_id_1 and p.get("participantId") != participant_id_1]
            enemy_champions_1 = [p.get("championName") for p in participants if p.get("teamId") != team_id_1]
            record["ally_champions_1"] = ally_champions_1
            record["enemy_champions_1"] = enemy_champions_1

            # Ally and enemy champions for p2
            team_id_2 = p2.get("teamId")
            participant_id_2 = p2.get("participantId")
            ally_champions_2 = [p.get("championName") for p in participants if p.get("teamId") == team_id_2 and p.get("participantId") != participant_id_2]
            enemy_champions_2 = [p.get("championName") for p in participants if p.get("teamId") != team_id_2]
            record["ally_champions_2"] = ally_champions_2
            record["enemy_champions_2"] = enemy_champions_2

            # Bounties and economy
            record["bounty_level_1"] = p1.get("bountyLevel")
            record["bounty_level_2"] = p2.get("bountyLevel")
            
            # Killing sprees
            record["largest_killing_spree_1"] = p1.get("largestKillingSpree")
            record["largest_killing_spree_2"] = p2.get("largestKillingSpree")
            record["largest_multi_kill_1"] = p1.get("largestMultiKill")
            record["largest_multi_kill_2"] = p2.get("largestMultiKill")
            record["multikills_1"] = p1.get("challenges", {}).get("multikills")
            record["multikills_2"] = p2.get("challenges", {}).get("multikills")

            # Damage profile
            record["physical_damage_dealt_1"] = p1.get("physicalDamageDealtToChampions")
            record["physical_damage_dealt_2"] = p2.get("physicalDamageDealtToChampions")
            record["magic_damage_dealt_1"] = p1.get("magicDamageDealtToChampions")
            record["magic_damage_dealt_2"] = p2.get("magicDamageDealtToChampions")
            record["true_damage_dealt_1"] = p1.get("trueDamageDealtToChampions")
            record["true_damage_dealt_2"] = p2.get("trueDamageDealtToChampions")
            record["physical_damage_taken_1"] = p1.get("physicalDamageTaken")
            record["physical_damage_taken_2"] = p2.get("physicalDamageTaken")
            record["magic_damage_taken_1"] = p1.get("magicDamageTaken")
            record["magic_damage_taken_2"] = p2.get("magicDamageTaken")
            record["true_damage_taken_1"] = p1.get("trueDamageTaken")
            record["true_damage_taken_2"] = p2.get("trueDamageTaken")
            record["total_damage_dealt_1"] = p1.get("totalDamageDealt")
            record["total_damage_dealt_2"] = p2.get("totalDamageDealt")
            record["damage_self_mitigated_1"] = p1.get("damageSelfMitigated")
            record["damage_self_mitigated_2"] = p2.get("damageSelfMitigated")

            # Objectives
            record["turret_takedowns_1"] = p1.get("turretTakedowns")
            record["turret_takedowns_2"] = p2.get("turretTakedowns")
            record["dragon_takedowns_1"] = p1.get("challenges", {}).get("dragonTakedowns")
            record["dragon_takedowns_2"] = p2.get("challenges", {}).get("dragonTakedowns")
            record["baron_takedowns_1"] = p1.get("challenges", {}).get("baronTakedowns")
            record["baron_takedowns_2"] = p2.get("challenges", {}).get("baronTakedowns")

            # Survivability
            record["longest_time_living_1"] = p1.get("longestTimeSpentLiving")
            record["longest_time_living_2"] = p2.get("longestTimeSpentLiving")

            # Experience
            record["champ_experience_1"] = p1.get("champExperience")
            record["champ_experience_2"] = p2.get("champExperience")

            # Time played
            record["time_played_1"] = p1.get("timePlayed")
            record["time_played_2"] = p2.get("timePlayed")

            # Damage metrics
            record["damage_dealt_1"] = p1.get("totalDamageDealtToChampions")
            record["damage_dealt_2"] = p2.get("totalDamageDealtToChampions")
            record["damage_taken_1"] = p1.get("totalDamageTaken")
            record["damage_taken_2"] = p2.get("totalDamageTaken")
            record["damage_to_objectives_1"] = p1.get("damageDealtToObjectives")
            record["damage_to_objectives_2"] = p2.get("damageDealtToObjectives")

            # Early game impact
            record["first_blood_kill_1"] = p1.get("firstBloodKill")
            record["first_blood_kill_2"] = p2.get("firstBloodKill")
            record["first_blood_assist_1"] = p1.get("firstBloodAssist")
            record["first_blood_assist_2"] = p2.get("firstBloodAssist")
            record['takedownsFirst25Minutes_1'] = p1.get("challenges", {}).get("takedownsFirst25Minutes")
            record['takedownsFirst25Minutes_2'] = p2.get("challenges", {}).get("takedownsFirst25Minutes")

            # Gold efficiency
            record["gold_per_minute_1"] = p1.get("challenges", {}).get("goldPerMinute")
            record["gold_per_minute_2"] = p2.get("challenges", {}).get("goldPerMinute")
            record['laningPhaseGoldExpAdvantage_1'] = p1.get("challenges", {}).get("laningPhaseGoldExpAdvantage")
            record['laningPhaseGoldExpAdvantage_2'] = p2.get("challenges", {}).get("laningPhaseGoldExpAdvantage")
            record['earlyLaningPhaseGoldExpAdvantage_1'] = p1.get("challenges", {}).get("earlyLaningPhaseGoldExpAdvantage")
            record['earlyLaningPhaseGoldExpAdvantage_2'] = p2.get("challenges", {}).get("earlyLaningPhaseGoldExpAdvantage")


            # XP advantage in lane
            record["xp_diff_per_minute_1"] = p1.get("challenges", {}).get("xpDiffPerMinute")
            record["xp_diff_per_minute_2"] = p2.get("challenges", {}).get("xpDiffPerMinute")

            # Vision metrics
            vision_score_1 = p1.get("visionScore", 0)
            vision_score_2 = p2.get("visionScore", 0)
            record["vision_score_1"] = round(vision_score_1 / (game_duration / 60), 2) if game_duration else 0
            record["vision_score_2"] = round(vision_score_2 / (game_duration / 60), 2) if game_duration else 0

            # Farming metrics
            cs_1 = p1.get("totalMinionsKilled", 0) + p1.get("neutralMinionsKilled", 0)
            cs_2 = p2.get("totalMinionsKilled", 0) + p2.get("neutralMinionsKilled", 0)
            record["cs_1"] = round(cs_1 / (game_duration / 60), 2) if game_duration else 0
            record["cs_2"] = round(cs_2 / (game_duration / 60), 2) if game_duration else 0

            #Jungle
            if lane == "JUNGLE":
                record['junglerKillsEarlyJungle_1'] = p1.get('challenges', {}).get('junglerKillsEarlyJungle')
                record['junglerKillsEarlyJungle_2'] = p2.get('challenges', {}).get('junglerKillsEarlyJungle')
                record['killsOnLanersEarlyJungleAsJungler'] = p1.get('challenges', {}).get('killsOnLanersEarlyJungleAsJungler')
                record['killsOnLanersEarlyJungleAsJungler_2'] = p2.get('challenges', {}).get('killsOnLanersEarlyJungleAsJungler')

            # Kill participation and other advanced stats
            record["kill_participation_1"] = p1.get("challenges", {}).get("killParticipation")
            record["kill_participation_2"] = p2.get("challenges", {}).get("killParticipation")
            record["cc_score_1"] = p1.get("timeCCingOthers")
            record["cc_score_2"] = p2.get("timeCCingOthers")
            record["gold_spent_1"] = p1.get("goldSpent")
            record["gold_spent_2"] = p2.get("goldSpent")

            # Summoner spells and runes
            runes_1, spells_1 = extract_runes_and_spells(p1)
            runes_2, spells_2 = extract_runes_and_spells(p2)
            record["runes_1"] = runes_1
            record["runes_2"] = runes_2
            record["summoner_spells_1"] = spells_1
            record["summoner_spells_2"] = spells_2

            # Extract item purchase timeline for each participant
            record["items_1"] = parse_item_events(timeline, p1.get("participantId"))
            record["items_2"] = parse_item_events(timeline, p2.get("participantId"))

            matchup_records.append(record)
    return matchup_records

# Summoner spells and rune extraction helper
def extract_runes_and_spells(participant):
    """
    Extract full runes and summoner spells from a participant's data.
    """
    runes = []
    perks = participant.get("perks", {})
    styles = perks.get("styles", [])
    for style in styles:
        selections = style.get("selections", [])
        for sel in selections:
            runes.append(sel.get("perk"))

    spells = [
        participant.get("summoner1Id"),
        participant.get("summoner2Id")
    ]
    return runes, spells

def parse_item_events(timeline, participant_id):
    """
    Parse timeline events to extract item purchase events for a given participant,
    categorizing them into early, mid, or late game based on the timestamp.
    """
    item_events = []
    frames = timeline.get("info", {}).get("frames", [])
    for frame in frames:
        events = frame.get("events", [])
        for event in events:
            event_type = event.get("type")
            if event_type in ["ITEM_PURCHASED", "ITEM_SOLD", "ITEM_UNDO", "ITEM_DESTROYED"] and event.get("participantId") == participant_id:
                timestamp = event.get("timestamp")
                if timestamp < EARLY_PHASE_THRESHOLD:
                    phase = "early"
                elif timestamp < MID_PHASE_THRESHOLD:
                    phase = "mid"
                else:
                    phase = "late"
                item_events.append({
                    "itemId": event.get("itemId"),
                    "timestamp": timestamp,
                    "phase": phase,
                    "action": event_type
                })
    return item_events
