# game_state.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class SummonerSpells:
    spell_one: str
    spell_two: str


@dataclass
class Score:
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    creep_score: int = 0
    ward_score: float = 0.0
    kda_string: str = field(init=False)

    @property
    def kda(self) -> float:
        return (self.kills + self.assists) / max(1, self.deaths)

    def __str__(self) -> str:
        # Format as "K/D/A (KDA Ratio)"
        return f"{self.kills}/{self.deaths}/{self.assists} ({self.kda:.1f})"

    def __post_init__(self):
        self.kda_string = self.__str__()


@dataclass
class ChampionState:
    name: str
    items: List[str]
    lane: Optional[str] = None
    level: int = 0
    score: Score = field(default_factory=Score)  # kills, deaths, assists, etc.
    is_bot: bool = False
    is_dead: bool = False
    respawn_timer: Optional[float] = None
    summoner_spells: Optional[SummonerSpells] = None

@dataclass
class Event:
    id: int
    name: str
    time: float
    dragonType: Optional[str] = None
    killer: Optional[str] = None
    victim: Optional[str] = None
    assisters: Optional[List[str]] = None
    turret: Optional[str] = None
    recipient: Optional[str] = None
    acer: Optional[str] = None
    acing_team: Optional[str] = None
    inhib: Optional[str] = None

@dataclass
class Monster:
    name: str
    type: str
    killed: Optional[float] = None
    team: Optional[str] = None
    spawn_time: Optional[float] = None
    death_time: Optional[float] = None
    respawn_timer: Optional[float] = None
    is_respawnable: bool = False
    ordinal: int = 0
    buff_expires_at: Optional[float] = None

@dataclass
class Monsters:
    monsters: List[Monster] = field(default_factory=list)

    def get_respawn_time(self, name: str, ordinal: int = 0) -> Optional[float]:
        for m in self.monsters:
            if m.name == name and m.ordinal == ordinal:
                return m.respawn_timer
        return None

    def get_taken_by_team(self, name: str, team: str) -> List[Monster]:
        return [m for m in self.monsters if m.name == name and m.team == team]

    def get_latest(self, name: str) -> Optional[Monster]:
        ms = [m for m in self.monsters if m.name == name]
        if not ms: return None
        return max(ms, key=lambda m: m.killed if m.killed is not None else -1)

@dataclass
class TeamState:
    champions: List[ChampionState]
    # total_gold: int = 0

    # New fields for structure tracking
    turrets_taken: Dict[str, List[str]] = field(default_factory=lambda: {"Bot": [], "Mid": [], "Top": []})
    inhibs_taken: List[str] = field(default_factory=list)
    num_turrets_taken: int = 0
    num_inhibs_taken: int = 0

    baron_buff_expires_at: Optional[float] = None
    elder_buff_expires_at: Optional[float] = None
    # New field: counts of each unique monster taken by this team
    monster_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class Structure:
    id: str
    id_raw: str
    team: str
    lane: str
    tier: str
    is_dead: bool = False
    respawn_timer: Optional[float] = None

@dataclass
class Structures:
    team: str
    turrets: Dict[str, Structure] = field(default_factory=dict)
    inhibitors: Dict[str, Structure] = field(default_factory=dict)

    def initialize_structures(self):
        # Initialize turrets and inhibitors for the team
        tiers = {"P3": "Outer", "P2": "Inner", "P1": "Inhibitor", "P4": "Nexus1", "P5": "Nexus2"}
        lanes = {"L0": "Bot", "L1": "Mid", "L2": "Top"}
        teams = {"ORDER": "T100", "CHAOS": "T200"}

        for lane_code, lane_name in lanes.items():
            for tier_code, tier_name in tiers.items():
                # Only allow "Nexus1" and "Nexus2" tiers for lane "Mid"
                if tier_name in ("Nexus1", "Nexus2") and lane_name != "Mid":
                    continue
                turret_id = f"Turret_{self.team}_{lane_name}_{tier_name}"
                turret_id_raw = f"Turret_{teams[self.team]}_{lane_code}_{tier_code}"
                self.turrets[turret_id_raw] = Structure(
                    id=turret_id, id_raw=turret_id_raw, team=self.team, lane=lane_name, tier=tier_name
                )

        for lane_code, lane_name in lanes.items():
            inhib_id = f"Inhib_{self.team}_{lane_name}_P1"
            inhib_id_raw = f"Inhib_{teams[self.team]}_{lane_code}_P1"
            self.inhibitors[inhib_id_raw] = Structure(
                id=inhib_id, id_raw=inhib_id_raw, team=self.team, lane=lane_name, tier="Inhibitor"
            )

    def update_from_events(self, events: List[Event], game_time: float):
        # Track the latest destroy time for each inhib and nexus turret
        latest_inhib_destroy = {}
        latest_nexus_turret_destroy = {}

        for event in events:
            if event.name == "TurretKilled":
                turret_id = event.turret
                base_turret_id = "_".join(turret_id.split("_")[:4]) if turret_id else None
                turret = self.turrets.get(base_turret_id)
                if turret:
                    turret.is_dead = True
                    # Track latest destroy time for Nexus turrets
                    if "Nexus" in (turret.tier or "") or ("Nexus" in (turret.id or "")):
                        prev_time = latest_nexus_turret_destroy.get(base_turret_id, -1)
                        if event.time > prev_time:
                            latest_nexus_turret_destroy[base_turret_id] = event.time
                        # Set respawn timer
                        turret.respawn_timer = event.time + 180  # 3 min
            elif event.name == "InhibKilled":
                inhib_id = event.inhib
                base_inhib_id = "_".join(inhib_id.split("_")[:4]) if inhib_id else None
                inhib = self.inhibitors.get(base_inhib_id)
                if inhib:
                    inhib.is_dead = True
                    prev_time = latest_inhib_destroy.get(base_inhib_id, -1)
                    if event.time > prev_time:
                        latest_inhib_destroy[base_inhib_id] = event.time
                    inhib.respawn_timer = event.time + 300  # 5 min
            elif event.name == "InhibRespawned":
                inhib_id = event.inhib
                base_inhib_id = "_".join(inhib_id.split("_")[:4]) if inhib_id else None
                inhib = self.inhibitors.get(base_inhib_id)
                if inhib:
                    inhib.is_dead = False
                    inhib.respawn_timer = None

        # After processing events, update all structures for respawn logic
        for inhib in self.inhibitors.values():
            if inhib.is_dead and inhib.respawn_timer is not None:
                if game_time > inhib.respawn_timer:
                    inhib.is_dead = False
                    inhib.respawn_timer = None
        for turret in self.turrets.values():
            # Only Nexus turrets can respawn
            if turret.is_dead and turret.respawn_timer is not None:
                if "Nexus" in (turret.tier or ""):
                    if game_time > turret.respawn_timer:
                        turret.is_dead = False
                        turret.respawn_timer = None

@dataclass
class ChampionStats:
    health: float
    mana: float
    armor: float
    magic_resist: float
    attack_damage: float
    attack_speed: float
    ability_haste: float
    movement_speed: float

@dataclass
class Item:
    name: str
    item_id: int
    slot: int
    count: int
    price: int
    consumable: bool
    can_use: bool

@dataclass
class Rune:
    name: str

@dataclass
class Runes:
    keystone: Optional[Rune]
    primary: Optional[str]
    secondary: Optional[str]
    full_runes: Optional[List[Rune]] = None  # Only for the active player

@dataclass
class ObjectiveTimers:
    baron_respawn: Optional[float] = None
    herald_respawn: Optional[float] = None
    dragon_respawn: Optional[float] = None
    dragon_type: Optional[str] = None

    def update_from_events(self, events: List[Event], game_time: float):
        # Method intentionally left blank; use update_from_monsters instead.
        pass

    def update_from_monsters(self, monsters: Monsters, game_time: float):
        # DRAGON
        latest_dragon = monsters.get_latest("Dragon")
        self.dragon_type = latest_dragon.type if latest_dragon and latest_dragon.ordinal > 3 else None
        if latest_dragon is not None and latest_dragon.respawn_timer is not None:
            self.dragon_respawn = latest_dragon.respawn_timer
        else:
            self.dragon_respawn = 300.0

        # HERALD
        latest_herald = monsters.get_latest("Herald")
        if latest_herald is not None and latest_herald.respawn_timer is not None:
            self.herald_respawn = latest_herald.respawn_timer
        else:
            self.herald_respawn = 900.0 if game_time < 1500 else None

        # BARON
        latest_baron = monsters.get_latest("Baron")
        if latest_baron is not None and latest_baron.respawn_timer is not None:
            self.baron_respawn = latest_baron.respawn_timer
        else:
            self.baron_respawn = 1500.0

@dataclass
class GameStateContext:
    timestamp: float
    player_team: TeamState
    enemy_team: TeamState
    objectives: ObjectiveTimers
    player_champion: str
    enemy_laner_champ: str
    role: str
    team_side: str

    active_player_stats: ChampionStats
    active_player_gold: float
    active_player_summoner_name: str
    active_player_riot_id: str
    active_player_idx: int
    active_player_runes: Runes
    enemy_laner_runes: Optional[Runes]

    events: List[Event]

    player_team_structures: Structures = field(default_factory=Structures)
    enemy_team_structures: Structures = field(default_factory=Structures)
    monsters: Monsters = field(default_factory=Monsters)


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
    counters = {mt["name"]: 1 for mt in monster_types}
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
                buff_expires_at = None

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
                        # Elder dragon buff lasts 150s
                        buff_expires_at = killed_time + 150
                    else:
                        respawn_timer = killed_time + mt["respawn"] if is_respawnable else None
                else:
                    # Non-dragon monsters: original logic
                    respawn_timer = killed_time + mt["respawn"] if mt["is_respawnable"] else None
                    # Baron buff lasts 180s
                    if mt["name"] == "Baron":
                        buff_expires_at = killed_time + 180
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
                    ordinal=ordinal,
                    buff_expires_at=buff_expires_at
                ))
    return Monsters(monsters=monsters)

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
        ) for p in members]
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
        m_type = m.type + " " if m.type else ""
        monster_counts[m_type + m.name] = monster_counts.get(m.name, 0) + 1
    team_state.monster_counts = monster_counts

    # Compute baron_buff_expires_at and elder_buff_expires_at
    barons = [m for m in monsters_taken if m.name == "Baron" and m.buff_expires_at is not None]
    elders = [m for m in monsters_taken if m.name == "Dragon" and m.type and m.type.lower() == "elder" and m.buff_expires_at is not None]
    baron_buff_expires_at = max((m.buff_expires_at for m in barons), default=None)
    elder_buff_expires_at = max((m.buff_expires_at for m in elders), default=None)
    # Attach to team_state if needed as new fields
    team_state.baron_buff_expires_at = baron_buff_expires_at
    team_state.elder_buff_expires_at = elder_buff_expires_at

    # total_gold = sum(p["scores"].get("creepScore", 0) * 21 + p["scores"].get("kills", 0) * 300 for p in members)
    # team_state.total_gold = total_gold
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

    enemy_laner_champ = next((p["champion"] for p in players if p["team"] == enemy_team_name and p.get("lane") == active.get("position")), None)
    # Try to match player's lane/role if possible
    active_lane = players[active_player_idx].get("lane") if active_player_idx is not None else None
    if not active_lane: #practice tool
        # fallback: use summoner spell type or champion position
        active_lane = next((p["lane"] for p in players if p["riot_id"] == active_player_riot_id and p["lane"]), "Mid")
    enemy_laner = next((p for p in players if p["team"] == enemy_team_name and p.get("lane") == active_lane), None)
    #print items for all players
    return GameStateContext(
        timestamp=game_state_json.get("gameData", {}).get("gameTime", 0),
        player_team=player_team,
        enemy_team=enemy_team,
        objectives=objectives,
        player_champion=players[active_player_idx].get("champion") if active_player_idx is not None else "",
        enemy_laner_champ=enemy_laner_champ,
        role=active_lane,
        team_side=player_team_name,
        active_player_idx=active_player_idx,
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
