"""Input schema describing information expected from a BUR source."""

# schemas/entry/source_expectation.py

from enums.expected_information import ExpectedInformationType
from common import BurInputModel, ExternalRef


class BurSourceExpectationIn(BurInputModel):
    """Validate an expected-information declaration for a source.

    :ivar expectation_ref: Stable external reference to the expectation.
    :ivar project_source_ref: Stable external reference to the project source.
    :ivar section_ref: Stable external reference to the section.
    :ivar information_type: Information type.
    :ivar required: Required.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    expectation_ref: ExternalRef

    project_source_ref: ExternalRef
    section_ref: ExternalRef | None = None

    information_type: ExpectedInformationType

    required: bool = False
    notes: str | None = None
