"""A data model for quickstatements."""

import datetime
import logging
import webbrowser
from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Annotated, Literal, get_args
from urllib.parse import quote

from pydantic import BaseModel, Field
from wikibaseintegrator.wbi_enums import WikibaseDatatype

logger = logging.getLogger(__name__)


def _safe_field(*, regex: str | None = None, **kwargs) -> Field:
    try:
        rv = Field(regex=regex, **kwargs)
    except TypeError:
        rv = Field(pattern=regex, **kwargs)
    return rv


class CalendarModels(str, Enum):
    """
    Wikidata Calendar Models
    """

    JULIAN = "http://www.wikidata.org/entity/Q1985786"
    GREGORIAN = "http://www.wikidata.org/entity/Q1985727"


class Qualifier(BaseModel):
    """
    A qualifier
    """

    type: str = "String"
    predicate: str = _safe_field(regex=r"^!?[PQS]\d+$")
    target: str

    def get_target(self) -> str:
        """Get the target wikidata identifier."""
        return self.target


class EntityQualifier(Qualifier):
    """A qualifier that points to Wikidata entity."""

    type: Literal["Entity"] = "Entity"
    target: str = _safe_field(regex=r"^[PQS]\d+$")


class DateQualifier(Qualifier):
    """A qualifier that points to a date string."""

    type: Literal["Date"] = "Date"

    @classmethod
    def point_in_time(
        cls,
        target: str | datetime.datetime | datetime.date,
        *,
        precision: int | None = None,
    ) -> "DateQualifier":
        """Get a qualifier for a point in time."""
        return cls(predicate="P585", target=prepare_date(target, precision=precision))

    @classmethod
    def start_time(
        cls,
        target: str | datetime.datetime | datetime.date,
        *,
        precision: int | None = None,
    ) -> "DateQualifier":
        """Get a qualifier for a start time."""
        return cls(predicate="P580", target=prepare_date(target, precision=precision))

    @classmethod
    def end_time(
        cls,
        target: str | datetime.datetime | datetime.date,
        *,
        precision: int | None = None,
    ) -> "DateQualifier":
        """Get a qualifier for an end time."""
        return cls(predicate="P582", target=prepare_date(target, precision=precision))

    @classmethod
    def retrieved(cls, namespace: Literal["P", "S"], precision: int | None = 11) -> "DateQualifier":
        """Get a qualifier for retrieving data now."""
        # FIXME this doesn't appear to work with higher granularity like 14
        now = datetime.datetime.now()
        return cls(predicate=f"{namespace}813", target=prepare_date(now, precision=precision))


def format_date(
    *,
    precision: int,
    year: int,
    month: int = 0,
    day: int = 0,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> str:
    """Format the date in a way appropriate for quickstatements."""
    return f"+{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z/{precision}"


def prepare_date(
    target: str | datetime.datetime | datetime.date, *, precision: int | None = None, calendar: str | None = None
) -> str:
    """Prepare a date for quickstatements."""
    if isinstance(target, str):
        precision_def = f"/{precision}" if precision else ""
        if precision_def not in target:
            target += precision_def
        if calendar is not None and CalendarModels(calendar) is CalendarModels.JULIAN:
            target += "/J"
        return target
    if not isinstance(target, datetime.datetime | datetime.date):
        raise TypeError
    if precision is None:
        precision = 11
    if isinstance(target, datetime.date) and precision > 11:
        precision = 11
        logger.warning("Can not have higher precision on a datetime.date input than 11")
    # See section on precision in https://www.wikidata.org/wiki/Help:Dates#Precision
    if precision == 11:  # day precision
        return format_date(precision=precision, year=target.year, month=target.month, day=target.day)
    elif precision == 10:  # month precision
        return format_date(precision=precision, year=target.year, month=target.month)
    elif precision == 9:  # year precision
        return format_date(precision=precision, year=target.year)
    elif precision == 12:  # hour precision
        if not isinstance(target, datetime.datetime):
            raise RuntimeError
        return format_date(
            precision=precision,
            year=target.year,
            month=target.month,
            day=target.day,
            hour=target.hour,
        )
    elif precision == 13:  # minute precision
        if not isinstance(target, datetime.datetime):
            raise RuntimeError
        return format_date(
            precision=precision,
            year=target.year,
            month=target.month,
            day=target.day,
            hour=target.hour,
            minute=target.minute,
        )
    elif precision == 14:  # second precision
        if not isinstance(target, datetime.datetime):
            raise RuntimeError
        return format_date(
            precision=precision,
            year=target.year,
            month=target.month,
            day=target.day,
            hour=target.hour,
            minute=target.minute,
            second=target.second,
        )
    else:
        raise ValueError(f"Invalid precision: {precision}")
    # No precision case:
    # return f"+{target.isoformat()}Z"


class TextQualifier(Qualifier):
    """A qualifier that points to a string literal."""

    type: Literal["Text"] = "Text"

    def get_target(self) -> str:
        """Get the target text literal."""
        return f'"{self.target}"'


class TimeQualifier(DateQualifier):
    """A line whose target is a date/datetime."""

    precision: int | None = None
    calendar: str | None = None

    def get_target(self) -> str:
        """Get the date literal line."""
        return prepare_date(self.target, precision=self.precision, calendar=self.calendar)


class MonolingualTextQualifier(TextQualifier):
    """A qualifier whose target is a monolingual string."""

    language: str

    def get_target(self) -> str:
        """Get the target text literal."""
        return f'{self.language}:"{self.target}"'


class QuantityQualifier(Qualifier):
    type: Literal["Quantity"] = "Quantity"
    unit: str | None = _safe_field(regex=r"^[Q]\d+$")
    tolerance: str | None = None

    def get_target(self) -> str:
        """Get the target text literal."""
        res = f"{self.target}"
        if self.tolerance is not None:
            res += f"~{self.tolerance}"
        if self.unit is not None:
            unit = self.unit.replace("Q", "U")
            res += unit
        return res


class CreateLine(BaseModel):
    """A trivial model representing the CREATE line."""

    type: Literal["Create"] = "Create"

    def get_line(self, sep: str = "|") -> str:
        """Get the CREATE line."""
        return "CREATE"


class CreatePropertyLine(BaseModel):
    """A trivial model representing the CREATE line."""

    datatype: WikibaseDatatype
    type: Literal["Create"] = "Create"

    def get_line(self, sep: str = "|") -> str:
        """Get the CREATE line."""
        return f"CREATE_PROPERTY{sep}{self.datatype.value}"


class BaseLine(BaseModel):
    """A shared model for entity and text lines."""

    subject: str = _safe_field(regex=r"^(LAST)|(Q\d+)$")
    predicate: str = _safe_field(
        regex=r"^(P\d+)|([ADL][a-z]+)|(S\w+)$",
        description="""\
        The predicate can be one of two things:

        1. A Wikidata predicate, which starts with an upper case letter P, followed by a sequence of digits
        2. A combination of a single letter command code and an ISO639 language code.
           The single letter command codes can be:
           - ``L`` for label
           - ``A`` for alias (i.e., synonym)
           - ``D`` for description
           - ``S`` for sidelinks
           See Wikidata documentation at https://www.wikidata.org/w/index.php?title=Help:QuickStatements&\
section=6#Adding_labels,_aliases,_descriptions_and_sitelinks

        To do: add support for sitelinks.
        """,
    )
    qualifiers: list[Qualifier] = Field(default_factory=list)

    def get_target(self) -> str:
        """Get the target of the line."""
        return self.target

    def get_line(self, sep: str = "|") -> str:
        """Get the QuickStatement line as a string."""
        parts = [self.subject, self.predicate, self.get_target()]
        for qualifier in self.qualifiers:
            parts.append(qualifier.predicate)
            parts.append(qualifier.get_target())
        return sep.join(parts)


class EntityLine(BaseLine):
    """A line whose target is a string literal."""

    type: Literal["Entity"] = "Entity"
    target: str = _safe_field(regex=r"^[PQ]\d+$")


class TextLine(BaseLine):
    """A line whose target is a Wikidata entity."""

    type: Literal["Text"] = "Text"
    target: str

    def get_target(self) -> str:
        """Get the text literal line."""
        return f'"{self.target}"'


class MonolingualTextLine(TextLine):
    """A qualifier whose target is a monolingual string."""

    language: str

    def get_target(self) -> str:
        """Get the target text literal."""
        return f'{self.language}:"{self.target}"'


class QuantityLine(BaseLine):
    type: Literal["Quantity"] = "Quantity"
    target: str
    unit: str | None = _safe_field(regex=r"^[Q]\d+$")
    tolerance: str | None = None

    def get_target(self) -> str:
        """Get the target text literal."""
        res = f"{self.target}"
        if self.tolerance is not None:
            res += f"~{self.tolerance}"
        if self.unit is not None:
            unit = self.unit.replace("Q", "U")
            res += unit
        return res


class DateLine(BaseLine):
    """A line whose target is a date/datetime."""

    type: Literal["Date"] = "Date"
    target: datetime.datetime | datetime.date | str
    precision: int | None = None
    calendar: str | None = None

    def get_target(self) -> str:
        """Get the date literal line."""
        return prepare_date(self.target, precision=self.precision, calendar=self.calendar)


#: A union of the line types
Line = Annotated[CreateLine | EntityLine | TextLine | DateLine, Field(discriminator="type")]


def render_lines(lines: Iterable[Line], sep: str = "|", newline: str = "||") -> str:
    """Prepare QuickStatements line objects for sending to the API."""
    return newline.join(line.get_line(sep=sep) for line in lines)


def lines_to_url(lines: Iterable[Line]) -> str:
    """Prepare a URL for V1 of QuickStatements."""
    quoted_qs = quote(render_lines(lines), safe="")
    return f"https://quickstatements.toolforge.org/#/v1={quoted_qs}"


def lines_to_new_tab(lines: Iterable[Line]) -> bool:
    """Open a web browser on the host system.

    :param lines: QuickStatements lines
    :returns: If a web browser was successfully invoked (via :func:`webbrowser.open`)
    """
    lines = list(lines)
    if not lines:
        return False
    return webbrowser.open_new_tab(lines_to_url(lines))


def _unpack_annotated(t) -> Sequence[type]:
    return get_args(get_args(t)[0])


def write_json_schema():
    """Write a JSON schema."""
    import json

    import pydantic.schema

    schema = pydantic.schema.schema(
        [
            *_unpack_annotated(Qualifier),
            *_unpack_annotated(Line),
        ],
        title="QuickStatements",
        description="A data model representing lines in Quickstatements",
    )
    with open("schema.json", "w") as file:
        json.dump(schema, file, indent=2)


if __name__ == "__main__":
    write_json_schema()
