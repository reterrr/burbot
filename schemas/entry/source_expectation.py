# schemas/entry/source_expectation.py

from enums.expected_information import ExpectedInformationType
from common import BurInputModel, ExternalRef


class BurSourceExpectationIn(BurInputModel):
    expectation_ref: ExternalRef

    project_source_ref: ExternalRef
    section_ref: ExternalRef | None = None

    information_type: ExpectedInformationType

    required: bool = False
    notes: str | None = None
