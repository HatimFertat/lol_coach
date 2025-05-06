# parsers.py

from typing import List, Dict, Optional, Any
from game_state.models import (ChampionState, ChampionStats, Event, Item, SummonerSpells, Score, Rune, Runes,
                                Structures, Monsters, Monster, ObjectiveTimers, TeamState, GameStateContext)


def parse_monsters(events: List[Event], players_team: Optional[List[Dict[str, Any]]]) -> Monsters:
    """
    Parse monster kills from event log and build monster objects with timings and metadata.
    If a players list is provided, use riot_id to team mapping for monster team assignment.
    Enhanced logic for DragonKill events to handle respawnable status and respawn times.
    """
    monster_types = [
        {"event": "DragonKill", "name": "Dragon", "respawn": 300, "is_respawnable": True},
        {"event": "BaronKill", "name": "Baron", "respawn": 420, "is_respawnable": True},
        {"event": "HeraldKill", "name": "Herald", "respawn": 360, "is_respawnable": False},
        # Add Elder, Rift, etc. as needed
    ]
    monsters: List[Monster] = []
    counters = {mt["name"]: 0 for mt in monster_types}
    last_respawn = {mt["name"]: None for mt in monster_types}
    # Track number of dragons taken by each team
    dragons_per_team: Dict[str, int] = {}
    for event in events:
        for mt in monster_types:
            if event.name == mt["event"]:
                monster_type = event.dragonType
                ordinal = counters[mt["name"]]
                killed_time = event.time
                # Determine team from killer riot_id if possible
                team = None
                if event.killer and players_team:
                    team = players_team.get(event.killer)
                if not team:
                    team = event.killer
                spawn_time = last_respawn[mt["name"]] if last_respawn[mt["name"]] is not None else 0.0
                death_time = killed_time
                respawn_timer = None
                is_respawnable = mt["is_respawnable"]

                if event.name == "DragonKill":
                    # Count dragons per team
                    if team not in dragons_per_team:
                        dragons_per_team[team] = 0
                    dragons_per_team[team] += 1
                    # If this is the 4th dragon for the team (i.e., just reached 4), set is_respawnable = False
                    if dragons_per_team[team] == 4:
                        is_respawnable = False
                    # Elder dragon: respawn in 360s, not 300s
                    if monster_type and monster_type.lower() == "elder":
                        respawn_timer = killed_time + 360 if is_respawnable else None
                    else:
                        respawn_timer = killed_time + mt["respawn"] if is_respawnable else None
                    counters[mt["name"]] += 1
                    last_respawn[mt["name"]] = respawn_timer
                else:
                    # Non-dragon monsters: original logic
                    respawn_timer = killed_time + mt["respawn"] if mt["is_respawnable"] else None
                    counters[mt["name"]] += 1
                    last_respawn[mt["name"]] = respawn_timer
                monsters.append(Monster(
                    name=mt["name"],
                    type=monster_type,
                    killed=killed_time,
                    team=team,
                    spawn_time=spawn_time,
                    death_time=death_time,
                    respawn_timer=respawn_timer,
                    is_respawnable=is_respawnable,
                    ordinal=ordinal
                ))
    return Monsters(monsters=monsters)

def parse_champion_stats(stats_json: Dict[str, Any]) -> ChampionStats:
    return ChampionStats(
        health=stats_json.get("health", 0),
        mana=stats_json.get("mana", 0),
        armor=stats_json.get("armor", 0),
        magic_resist=stats_json.get("magicResist", 0),
        attack_damage=stats_json.get("attackDamage", 0),
        attack_speed=stats_json.get("attackSpeed", 0),
        ability_haste=stats_json.get("abilityHaste", 0),
        movement_speed=stats_json.get("moveSpeed", 0)
    )

def parse_event(event_json: Dict[str, Any]) -> Event:
    return Event(
        id=event_json.get("EventID", 0),
        name=event_json.get("EventName", ""),
        time=event_json.get("EventTime", 0),
        dragonType=event_json.get("DragonType", ""),
        killer=event_json.get("KillerName"),
        victim=event_json.get("VictimName"),
        assisters=event_json.get("Assisters"),
        turret=event_json.get("TurretKilled"),
        recipient=event_json.get("Recipient"),
        acer=event_json.get("Acer"),
        acing_team=event_json.get("AcingTeam"),
        inhib=event_json.get("InhibKilled")
    )

def parse_item(item_json: Dict[str, Any]) -> Item:
    return Item(
        name=item_json.get("displayName", ""),
        item_id=item_json.get("itemID", 0),
        slot=item_json.get("slot", 0),
        count=item_json.get("count", 1),
        price=item_json.get("price", 0),
        consumable=item_json.get("consumable", False),
        can_use=item_json.get("canUse", False)
    )

def parse_items(items_json: List[Dict[str, Any]]) -> List[Item]:
    return [parse_item(i) for i in items_json]

def parse_summoner_spells(spells_json: Dict[str, Any]) -> SummonerSpells:
    return SummonerSpells(
        spell_one=spells_json.get("summonerSpellOne", {}).get("displayName", ""),
        spell_two=spells_json.get("summonerSpellTwo", {}).get("displayName", "")
    )

def parse_score(score_json: Dict[str, Any]) -> Score:
    score = Score(
        kills=score_json.get("kills", 0),
        deaths=score_json.get("deaths", 0),
        assists=score_json.get("assists", 0),
        creep_score=score_json.get("creepScore", 0),
        ward_score=score_json.get("wardScore", 0.0)
    )
    return score

def parse_runes(runes_json: Dict[str, Any], is_active_player: bool = False) -> Runes:
    keystone_data = runes_json.get("keystone", {})
    keystone = Rune(name=keystone_data.get("displayName", "")) if "displayName" in keystone_data else None
    primary = runes_json.get("primaryRuneTree", {}).get("displayName", "")
    secondary = runes_json.get("secondaryRuneTree", {}).get("displayName", "")
    full_runes = None

    if is_active_player and "generalRunes" in runes_json:
        full_runes = [
            Rune(name=rune.get("displayName", "")) for rune in runes_json.get("generalRunes", [])
        ]

    return Runes(
        keystone=keystone,
        primary=primary,
        secondary=secondary,
        full_runes=full_runes
    )

def parse_player_state(player_json: Dict[str, Any]) -> Dict[str, Any]:
    # Returns a dict with all fields that PlayerState would have had, plus runes as dict
    runes = parse_runes(player_json.get("runes", {}), is_active_player="fullRunes" in player_json)

    return {
        "name": player_json.get("summonerName", ""),
        "riot_id": player_json.get("riotIdGameName", ""),
        "champion": player_json.get("championName", ""),
        "level": player_json.get("level", 0),
        "is_bot": player_json.get("isBot", False),
        "is_dead": player_json.get("isDead", False),
        "team": player_json.get("team", ""),
        "lane": player_json.get("position"),
        "items": parse_items(player_json.get("items", [])),
        "runes": runes,
        "summoner_spells": parse_summoner_spells(player_json.get("summonerSpells", {})),
        "scores": player_json.get("scores", {}),
        "respawn_timer": player_json.get("respawnTimer", 0)
    }

def parse_team_state(
    team_name: str,
    all_players: List[Dict[str, Any]],
    events: List[Event],
    enemy_structures: Structures = None,
    monsters: Monsters = None
) -> TeamState:
    members = [p for p in all_players if p.get("team") == team_name]
    team_state = TeamState(
        champions=[ChampionState(
            name=p["champion"],
            items=[item.name for item in p.get("items", [])],
            lane=p["lane"],
            level=p["level"],
            score=parse_score(p.get("scores", {})),
            is_bot=p.get("is_bot", False),
            is_dead=p.get("is_dead", False),
            respawn_timer=p.get("respawn_timer"),
            summoner_spells=p.get("summoner_spells"),
        ) for p in members],
        total_gold=0 #update at the end
    )

    # Compute turrets_taken and inhibs_taken from enemy_structures
    if enemy_structures is not None:
        turrets_taken = {"Bot": [], "Mid": [], "Top": []}
        for t in enemy_structures.turrets.values():
            if t.is_dead:
                # Only categorize lane turrets (Bot, Mid, Top)
                if t.lane in turrets_taken:
                    turrets_taken[t.lane].append(t.tier)
        team_state.turrets_taken = turrets_taken
        # Inhibitors taken: lane for each dead inhib
        inhibs_taken = []
        for inhib in enemy_structures.inhibitors.values():
            if inhib.is_dead:
                inhibs_taken.append(inhib.lane)
        team_state.inhibs_taken = inhibs_taken
        # Count
        team_state.num_turrets_taken = sum(len(l) for l in turrets_taken.values())
        team_state.num_inhibs_taken = len(inhibs_taken)

    # Build monsters_taken for local computation, but do not store in TeamState
    monsters_taken = []
    if monsters is not None:
        monster_names = list(set(m.name for m in monsters.monsters))
        for monster_name in monster_names:
            monsters_taken.extend(monsters.get_taken_by_team(monster_name, team_name))

    # Compute monster_counts: map each unique monster name to its count
    monster_counts: Dict[str, int] = {}
    for m in monsters_taken:
        monster_counts[m.type + m.name] = monster_counts.get(m.name, 0) + 1
    team_state.monster_counts = monster_counts

    total_gold = sum(p["scores"].get("creepScore", 0) * 21 + p["scores"].get("kills", 0) * 300 for p in members)
    return team_state

def parse_objective_timers(game_state_json: Dict[str, Any], events: List[Event], monsters: Monsters = None) -> ObjectiveTimers:
    game_time = game_state_json.get("gameData", {}).get("gameTime", 0)
    timers = ObjectiveTimers()
    # Use monsters if provided, else fallback to old event-based (should always use monsters)
    if monsters is not None:
        timers.update_from_monsters(monsters, game_time)
    else:
        timers.update_from_events(events, game_time)
    return timers

def parse_turret_identifier(turret_id: str):
    """
    Parse the turret identifier to extract team, lane, and tier information.
    """
    parts = turret_id.split("_")
    if len(parts) < 4:
        return None

    team = "ORDER" if parts[1] == "T100" else "CHAOS"
    lane_map = {"L0": "Bot", "L1": "Mid", "L2": "Top", "Bot": "Bot", "Mid": "Mid", "Top": "Top"}
    tier_map = {"P3": "Outer", "P2": "Inner", "P1": "Inhibitor", "P4": "Nexus1", "P5": "Nexus2",
            "Outer": "Outer", "Inner": "Inner", "Inhibitor": "Inhibitor", "Nexus1": "Nexus1", "Nexus2": "Nexus2"}

    lane = lane_map.get(parts[2])
    tier = tier_map.get(parts[3])
    if not lane or not tier:
        return None

    return {"team": team, "lane": lane, "tier": tier}

def count_turrets_taken(events: List[Event]):
    """
    Count turrets taken by each team and categorize them by lane and tier.
    """
    turrets_taken = {
        "ORDER": {"Bot": [], "Mid": [], "Top": []},
        "CHAOS": {"Bot": [], "Mid": [], "Top": []}
    }

    for event in events:
        if event.name == "TurretKilled":
            turret_info = parse_turret_identifier(event.turret)
            if turret_info:
                team = turret_info["team"]
                lane = turret_info["lane"]
                tier = turret_info["tier"]
                turrets_taken[team][lane].append(tier)

    return turrets_taken
def players_team_lookup(players: List[Dict[str, Any]]):
    # Build riot_id -> team lookup if players provided
    players_by_riot_id = {}
    if players is not None:
        for p in players:
            riot_id = p.get("riot_id")
            team = p.get("team")
            if riot_id and team:
                players_by_riot_id[riot_id] = team
    return players_by_riot_id

def parse_game_state(game_state_json: Dict[str, Any]) -> GameStateContext:
    events = [parse_event(e) for e in game_state_json.get("events", {}).get("Events", [])]
    players = [parse_player_state(p) for p in game_state_json.get("allPlayers", []) if p.get("championName") != ""]
    players_team = players_team_lookup(players)

    active = game_state_json.get("activePlayer", {})
    stats = parse_champion_stats(active.get("championStats", {}))
    current_gold = active.get("currentGold", 0.0)
    # Parse runes for the active player
    active_player_runes = parse_runes(active.get("fullRunes", {}), is_active_player=True)
    # Find player team and enemy team names
    active_player_riot_id = active.get("riotIdGameName", "")
    active_player_idx = next((i for i, p in enumerate(players) if p["riot_id"] == active_player_riot_id), None)
    player_team_name = players[active_player_idx]["team"] if players else ""
    enemy_team_name = "ORDER" if player_team_name == "CHAOS" else "CHAOS"

    # Initialize structures for both teams
    player_team_structures = Structures(team=player_team_name)
    enemy_team_structures = Structures(team=enemy_team_name)

    # Populate structures with initial data
    player_team_structures.initialize_structures()
    enemy_team_structures.initialize_structures()

    # Update structures based on events
    player_team_structures.update_from_events(events, game_state_json.get("gameData", {}).get("gameTime", 0))
    enemy_team_structures.update_from_events(events, game_state_json.get("gameData", {}).get("gameTime", 0))

    # Monsters: pass players for riot_id->team mapping
    monsters = parse_monsters(events, players_team=players_team)

    player_team = parse_team_state(player_team_name, players, events, enemy_structures=enemy_team_structures, monsters=monsters)
    enemy_team = parse_team_state(enemy_team_name, players, events, enemy_structures=player_team_structures, monsters=monsters)
    objectives = parse_objective_timers(game_state_json, events, monsters=monsters)

    # Try to match player's lane/role if possible
    active_lane = players[active_player_idx].get("lane") if active_player_idx is not None else None
    if not active_lane: #practice tool
        # fallback: use summoner spell type or champion position
        active_lane = next((p["lane"] for p in players if p["riot_id"] == active_player_riot_id and p["lane"]), "Mid")
    enemy_laner = next((p for p in players if p["team"] == enemy_team_name and p.get("lane") == active_lane), None)
    #print items for all players
    print([])
    return GameStateContext(
        timestamp=game_state_json.get("gameData", {}).get("gameTime", 0),
        player_team=player_team,
        enemy_team=enemy_team,
        objectives=objectives,
        player_champion=players[active_player_idx].get("champion") if active_player_idx is not None else "",
        role=active_lane,
        team_side=player_team_name,
        active_player_stats=stats,
        active_player_gold=current_gold,
        active_player_summoner_name=active.get("summonerName", ""),
        active_player_riot_id=active.get("riotIdGameName", ""),
        active_player_runes=active_player_runes,
        enemy_laner_runes=enemy_laner.get("runes") if enemy_laner else None,
        events=events,
        player_team_structures=player_team_structures,
        enemy_team_structures=enemy_team_structures,
        monsters=monsters
    )
