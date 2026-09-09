class TaskError(Exception):
    pass


class WorkflowNotFound(TaskError):
    def __init__(self, workflow_id: int) -> None:
        super().__init__(
            f"Workflow {workflow_id} not found"
        )


class CurrentWorkflowNotFound(TaskError):
    def __init__(self, source_id: int) -> None:
        super().__init__(
            f"Current workflow for source {source_id} not found"
        )


class TaskNotFound(TaskError):
    def __init__(self, task_id: int) -> None:
        super().__init__(
            f"Task {task_id} not found"
        )


class TaskConflict(TaskError):
    pass


class TaskValidationError(TaskError):
    pass
