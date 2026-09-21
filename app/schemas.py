"""Modele żądań API (Pydantic). Walidacja typów na wejściu; reguły domenowe pozostają w modułach."""

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, StrictBool

Radius = Union[int, float, str]


class Request(BaseModel):
    """Bazowy model: nieznane pola są ignorowane, tak jak w poprzedniej wersji API."""

    model_config = ConfigDict(extra='ignore')


class Empty(Request):
    pass


class PhotosPause(Request):
    paused: StrictBool


class ParallelMode(Request):
    mode: Literal['auto', '1', '2']


class ProfileSearch(Request):
    criteria: str


class ProfilesPause(Request):
    paused: StrictBool


class LocalAnalysis(Request):
    key: str
    criteria: str


class SyncRequest(Request):
    areas: str = ''
    radius: Radius = 40
    sources: list[str] = []


class LibraryRequest(Request):
    areas: str = ''
    radius: Radius = 40
    save_area: bool = False


class ImportRequest(Request):
    name: str = ''
    content: str = ''
    source: str = 'files'


class NoteRequest(Request):
    key: str
    choice: str = ''
    note: str = ''


class KeyRequest(Request):
    key: str


class CloudAnalysis(Request):
    key: str
    photos: StrictBool = False


class RankRequest(Request):
    dataset: Any = None
    areas: str = ''
    radius: Radius = 40


class OwnPlace(Request):
    """Własny punkt użytkownika: planowany, odwiedzony albo „na kiedyś”."""

    name: str
    lat: float
    lon: float
    status: Literal['planned', 'visited', 'someday'] = 'someday'
    description: str = ''
    note: str = ''
    url: str = ''
    key: str = ''  # ustawione = edycja istniejącego własnego punktu


class OwnPhoto(Request):
    key: str
    content: str  # base64
    caption: str = ''


class OwnPhotoDelete(Request):
    key: str
    url: str
