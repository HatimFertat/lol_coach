# models.py

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

# --- Monster Tracking ---
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
    total_gold: int

    # New fields for structure tracking
    turrets_taken: Dict[str, List[str]] = field(default_factory=lambda: {"Bot": [], "Mid": [], "Top": []})
    inhibs_taken: List[str] = field(default_factory=list)
    num_turrets_taken: int = 0
    num_inhibs_taken: int = 0

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

    def update_from_events(self, events: List[Event], game_time: float):
        # Method intentionally left blank; use update_from_monsters instead.
        pass

    def update_from_monsters(self, monsters: "Monsters", game_time: float):
        # DRAGON
        latest_dragon = monsters.get_latest("Dragon")
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
    role: str
    team_side: str

    active_player_stats: ChampionStats
    active_player_gold: float
    active_player_summoner_name: str
    active_player_riot_id: str
    active_player_runes: Runes
    enemy_laner_runes: Optional[Runes]

    events: List[Event]

    player_team_structures: Structures = field(default_factory=Structures)
    enemy_team_structures: Structures = field(default_factory=Structures)
    monsters: Monsters = field(default_factory=Monsters)
