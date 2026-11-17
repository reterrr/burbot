"""Edit these declarations and sample values to experiment with the language."""
SCHEMA = '''class ProjectStatus(Enum):
    PLANNED
    ACTIVE
    CLOSED

class Operator(Entity):
    name: String(persistent_key="name", nullable=False, unique=True, max_length=150)

class Project(Entity):
    name: String(persistent_key="name", nullable=False, unique=True)
    operator: Operator(persistent_key="operator", nullable=False)
    status: ProjectStatus(persistent_key="status", nullable=False, default=ProjectStatus.PLANNED)
    budget: Decimal(persistent_key="budget", precision=14, scale=2, ge=0, default="0.00")
    description: Text(persistent_key="description")
    enabled: Boolean(persistent_key="enabled", default=True)
    starts_at: DateTime(persistent_key="starts_at")
    external_id: UUID(persistent_key="external_id")
    settings: JSON(persistent_key="settings", default={})
    rating: Float(persistent_key="rating", ge=0, le=5, default=0)
    quantity: BigInteger(persistent_key="quantity", ge=0, default=0)
    source: Source(persistent_key="source")

class Recruitment(Entity):
    project: Reference(Project, persistent_key="project", nullable=False)
    closes_on: Date(persistent_key="closes_on")
'''

SEEDS = '''
operator = Operator(name="Example operator")
project = Project(
    name="Skills project",
    operator=operator,
    description="Persistent BusinessService walkthrough",
    starts_at="2026-11-01T09:00:00Z",
    external_id="11111111-1111-4111-8111-111111111111",
    settings={"regions": ["PL"], "remote": True},
)
recruitment = Recruitment(project=project, closes_on="2026-12-15")
'''

EVOLVED_SCHEMA = SCHEMA.replace(
    "    budget: Decimal",
    '    score: Integer(persistent_key="score", default=5, ge=0, le=100)\n'
    '    budget: Decimal',
)
