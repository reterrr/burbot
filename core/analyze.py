from db import TargetField, TokenClass
from db.enums import BusinessEntityType
from repositories import PhraseRepository, PatternRepository
from services.extraction.pattern_matcher import PatternMatcher
from sql_repository.extract import SqlModelPatternRepository

token_classes: list[TokenClass] = [
    TokenClass(
        name="TEXT",
        validation_regex=None,
        parser_name="parse_text",
        description="Arbitrary textual value.",
    ),
    TokenClass(
        name="INTEGER",
        validation_regex=r"^[+-]?\d+$",
        parser_name="parse_integer",
        description="Whole integer number.",
    ),
    TokenClass(
        name="DATE",
        validation_regex=None,
        parser_name="parse_date",
        description="Calendar date normalized to ISO 8601 format.",
    ),
    TokenClass(
        name="YEAR",
        validation_regex=r"^(19|20)\d{2}$",
        parser_name="parse_year",
        description="Four-digit calendar year.",
    ),
    TokenClass(
        name="QUARTER",
        validation_regex=r"^[1-4]$",
        parser_name="parse_quarter",
        description="Calendar quarter represented by a number from 1 to 4.",
    ),
    TokenClass(
        name="NIP",
        validation_regex=r"^\d{10}$",
        parser_name="parse_nip",
        description="Polish tax identification number normalized to ten digits.",
    ),
    TokenClass(
        name="IDENTIFIER",
        validation_regex=None,
        parser_name="parse_identifier",
        description="External business identifier, number, or code.",
    ),
    TokenClass(
        name="ENUM_VALUE",
        validation_regex=None,
        parser_name="parse_enum_value",
        description="Value belonging to a predefined business enumeration.",
    ),
    TokenClass(
        name="CURRENCY",
        validation_regex=r"^[A-Z]{3}$",
        parser_name="parse_currency",
        description="ISO 4217 currency code, for example PLN or EUR.",
    ),
    TokenClass(
        name="MONETARY_AMOUNT",
        validation_regex=None,
        parser_name="parse_monetary_amount",
        description=(
            "Monetary amount normalized to a decimal value without "
            "a currency symbol."
        ),
    ),
    TokenClass(
        name="PERCENTAGE",
        validation_regex=None,
        parser_name="parse_percentage",
        description=(
            "Percentage value normalized to a decimal number, "
            "for example 80.00."
        ),
    ),
]

token_class_ids: dict[str, int] = {
    token_class.name: token_class.id
    for token_class in token_classes
    if token_class.id is not None
}

fields: list[TargetField] = [
    # -------------------------------------------------------------------------
    # PROJECT
    # -------------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Project type stated in the sources, for example B2B or B2C."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.name",
        expected_type_id=token_class_ids["TEXT"],
        description="Official project or programme name stated in the sources.",
        required=True,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.number",
        expected_type_id=token_class_ids["IDENTIFIER"],
        description=(
            "Official project, programme or funding agreement number."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.status",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Current project status stated or implied by the sources."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.start_date",
        expected_type_id=token_class_ids["DATE"],
        description="Project implementation start date.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="projects.end_date",
        expected_type_id=token_class_ids["DATE"],
        description="Project implementation end date.",
        required=False,
    ),

    # -------------------------------------------------------------------------
    # OPERATOR
    # -------------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.OPERATOR,
        name="operators.name",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Official name of the institution or organization operating "
            "the project or recruitment."
        ),
        required=True,
    ),
    TargetField(
        entity_type=BusinessEntityType.OPERATOR,
        name="operators.nip",
        expected_type_id=token_class_ids["NIP"],
        description="Polish tax identification number of the operator.",
        required=False,
    ),

    # -------------------------------------------------------------------------
    # RECRUITMENT
    # -------------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.external_number",
        expected_type_id=token_class_ids["IDENTIFIER"],
        description=(
            "Official recruitment number or identifier, for example 2/2026."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.sequence_number",
        expected_type_id=token_class_ids["INTEGER"],
        description=(
            "Sequential number extracted from the recruitment identifier "
            "or stated separately in the sources."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.year",
        expected_type_id=token_class_ids["YEAR"],
        description=(
            "Calendar year assigned to the recruitment."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.status",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Current recruitment status stated or implied by the sources."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.start_date",
        expected_type_id=token_class_ids["DATE"],
        description="Date from which applications may be submitted.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.end_date",
        expected_type_id=token_class_ids["DATE"],
        description="Application submission deadline.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.announced_year",
        expected_type_id=token_class_ids["YEAR"],
        description=(
            "Announced recruitment year when exact application dates "
            "are not yet available."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.announced_quarter",
        expected_type_id=token_class_ids["QUARTER"],
        description=(
            "Announced recruitment quarter when exact application dates "
            "are not yet available."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.closed_status",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Structured closure outcome inferred from information in the sources."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitments.status_reason",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Explanation of the recruitment status, suspension, cancellation "
            "or closure."
        ),
        required=False,
    ),

    # -------------------------------------------------------------------------
    # GEOGRAPHY
    # -------------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.GEOGRAPHY,
        name="geographies.type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Administrative level associated with a geographical name, "
            "for example voivodeship, subregion, county or commune."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.GEOGRAPHY,
        name="geographies.name",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Name of a geographical area covered by the project "
            "or recruitment."
        ),
        required=True,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.currency",
        expected_type_id=token_class_ids["CURRENCY"],
        description="Currency used for project-level financial values.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.total_value",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Total value of the project.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.eligible_costs",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Total project costs eligible for public funding.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.public_funding_amount",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Total amount of public funding allocated to the project.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.own_contribution_amount",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Required own-contribution amount at project level.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.public_funding_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description="Project-level public funding percentage.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.public_funding_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Constraint applied to the public funding rate, such as "
            "exact, maximum or minimum."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.own_contribution_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description="Required own-contribution percentage at project level.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.own_contribution_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Constraint applied to the own-contribution rate, such as "
            "exact, maximum or minimum."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.max_support_per_participant",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one participant.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.max_support_per_company",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one company.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.max_support_per_service",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one service.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.max_eligible_service_cost",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum service cost that may be treated as eligible expenditure."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.max_eligible_hourly_rate",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum eligible cost for one hour of a service.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.aid_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Applicable state-aid classification, such as de minimis aid."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.funding_mechanism",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Mechanism through which project funding is provided."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.PROJECT,
        name="project_finances.vat_eligibility",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description="Rules determining whether VAT is an eligible cost.",
        required=False,
    ),

    # ---------------------------------------------------------------------
    # RECRUITMENT FINANCES
    # ---------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.currency",
        expected_type_id=token_class_ids["CURRENCY"],
        description=(
            "Currency used for recruitment-level financial values."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.allocation_amount",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Amount allocated directly to the recruitment."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.reserve_amount",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Financial reserve assigned to the recruitment.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.allocation_closure_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description=(
            "Percentage of the allocation at which the operator may "
            "suspend or close applications."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_support_per_application",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one application.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_support_per_participant",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one participant.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_support_per_company",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one company.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_support_per_service",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding available for one service.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_eligible_service_cost",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum service cost eligible under the recruitment."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.max_eligible_hourly_rate",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum eligible hourly rate under the recruitment."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.public_funding_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description="Public funding percentage for the recruitment.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.public_funding_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Constraint applied to the recruitment public funding rate."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.own_contribution_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description=(
            "Own-contribution percentage required by the recruitment."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.own_contribution_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Constraint applied to the recruitment own-contribution rate."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.aid_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description="State-aid classification applicable to the recruitment.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.funding_mechanism",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description="Funding mechanism applicable to the recruitment.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.RECRUITMENT,
        name="recruitment_finances.vat_eligibility",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "VAT eligibility rules applicable to the recruitment."
        ),
        required=False,
    ),

    # ---------------------------------------------------------------------
    # FUNDING RULE
    # ---------------------------------------------------------------------
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.beneficiary_type",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Type of beneficiary to which the financial rule applies."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.company_size",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Company-size category to which the financial rule applies."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.service_type",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Type of service to which the financial rule applies."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.target_group",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Target group that qualifies for the financial rule."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.condition_text",
        expected_type_id=token_class_ids["TEXT"],
        description=(
            "Additional eligibility conditions associated with the rule."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.public_funding_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description=(
            "Public funding percentage granted when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.public_funding_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description="Constraint applied to the rule's public funding rate.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.own_contribution_rate",
        expected_type_id=token_class_ids["PERCENTAGE"],
        description=(
            "Own-contribution percentage required when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.own_contribution_rate_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description=(
            "Constraint applied to the rule's own-contribution rate."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_support_per_application",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum funding per application when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_support_per_participant",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum funding per participant when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_support_per_company",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding per company when the rule matches.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_support_per_service",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description="Maximum funding per service when the rule matches.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_eligible_service_cost",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum eligible service cost when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.max_eligible_hourly_rate",
        expected_type_id=token_class_ids["MONETARY_AMOUNT"],
        description=(
            "Maximum eligible hourly rate when the rule matches."
        ),
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.aid_type",
        expected_type_id=token_class_ids["ENUM_VALUE"],
        description="State-aid type required or granted by the rule.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.valid_from",
        expected_type_id=token_class_ids["DATE"],
        description="Date from which the financial rule applies.",
        required=False,
    ),
    TargetField(
        entity_type=BusinessEntityType.FUNDING_RULE,
        name="funding_rules.valid_to",
        expected_type_id=token_class_ids["DATE"],
        description="Date until which the financial rule applies.",
        required=False,
    ),
]


# pobieramy wszystkie target fields
# na kazdy target_field mamy rules/patterns, najczesciej uzywanych phrases
# TODO: what html string is to big????
async def analyze_html(url: str, html: str):
    pattern_repository = SqlModelPatternRepository()
    pattern_matcher = PatternMatcher()

    for field in fields:
        if field.id is None:
            continue

        patterns = await pattern_repository.list_for_target_field(field.id)

        for pattern in patterns:
            if pattern.id is None:
                continue

            pattern_items = await pattern_repository.list_items(pattern.id)

            match = pattern_matcher.match(
                pattern=pattern,
                items=pattern_items,
                evidence=evidence_for_scope_instance,
            )

            if match is None:
                continue

            print(match.target_field_ids)
            print(match.element_ids)
            print(match.confidence)


async def analyze_pdf(path: str, descriptor: FileDescriptor):
    ...
