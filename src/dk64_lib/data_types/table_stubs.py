from typing import ClassVar, Mapping

from dk64_lib.data_types.base import BaseData


class StubTableData(BaseData):
    """Raw pointer table entry with a provisional semantic label."""

    table_id: ClassVar[int | None] = None
    table_name: ClassVar[str] = "Unparsed table data"
    description: ClassVar[str] = "Unparsed pointer table entry."
    notes: ClassVar[str] = ""
    known_entries: ClassVar[Mapping[int, str]] = {}

    def __post_init__(self):
        self.data_type = self.table_name


class MidiMusicData(StubTableData):
    table_id = 0
    table_name = "MIDI Music"
    description = "MIDI-style music sequence data."


class WallCollisionData(StubTableData):
    table_id = 2
    table_name = "Wall Collision"
    description = "Wall collision data."


class FloorCollisionData(StubTableData):
    table_id = 3
    table_name = "Floor Collision"
    description = "Floor collision data."


class ModelTwoGeometryData(StubTableData):
    table_id = 4
    table_name = "Model Two Geometry"
    description = "Model two geometry data; exact model category is not decoded yet."


class ActorGeometryData(StubTableData):
    table_id = 5
    table_name = "Actor Geometry"
    description = "Actor geometry data, likely including bones and texture references."


class SetupData(StubTableData):
    table_id = 9
    table_name = "Setup"
    description = "Setup data; exact contents are not decoded yet."


class InstanceScriptData(StubTableData):
    table_id = 10
    table_name = "Instance Script"
    description = "Instance script data."


class AnimationData(StubTableData):
    table_id = 11
    table_name = "Animation"
    description = (
        "Animation data. It is not yet known whether entries target textures, "
        "models, or both."
    )


class AnimationCodeData(StubTableData):
    table_id = 13
    table_name = "Animation Code"
    description = "Animation code data."


class PathData(StubTableData):
    table_id = 15
    table_name = "Path"
    description = "Path data."


class SpawnerData(StubTableData):
    table_id = 16
    table_name = "Spawner"
    description = "Spawner data."


class DKTVInputData(StubTableData):
    table_id = 17
    table_name = "DKTV Input"
    description = "DKTV input data."


class TriggerData(StubTableData):
    table_id = 18
    table_name = "Trigger"
    description = "Trigger data."


class UnknownTable19Data(StubTableData):
    table_id = 19
    table_name = "Unknown Table 19"
    description = "Unknown table with at least two text-like entries."
    known_entries = {
        4: "DK Rap lyrics",
        7: "End sequence credits",
    }


class AutowalkData(StubTableData):
    table_id = 21
    table_name = "Autowalk"
    description = "Autowalk data."


class CritterData(StubTableData):
    table_id = 22
    table_name = "Critter"
    description = "Critter data."


class ExitData(StubTableData):
    table_id = 23
    table_name = "Exit"
    description = "Map exit data."


class RaceCheckpointData(StubTableData):
    table_id = 24
    table_name = "Race Checkpoint"
    description = "Race checkpoint data."


class UncompressedFileSizeData(StubTableData):
    table_id = 26
    table_name = "Uncompressed File Size"
    description = "Uncompressed file size data."


STUB_TABLE_DATA_TYPES: dict[int, type[StubTableData]] = {
    data_type.table_id: data_type
    for data_type in (
        MidiMusicData,
        WallCollisionData,
        FloorCollisionData,
        ModelTwoGeometryData,
        ActorGeometryData,
        SetupData,
        InstanceScriptData,
        AnimationData,
        AnimationCodeData,
        PathData,
        SpawnerData,
        DKTVInputData,
        TriggerData,
        UnknownTable19Data,
        AutowalkData,
        CritterData,
        ExitData,
        RaceCheckpointData,
        UncompressedFileSizeData,
    )
}

