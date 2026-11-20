"""Register monitoring deployments in an existing Prefect 3 Process work pool."""

from prefect.flows import EntrypointType

from monitoring.flows import process_monitoring, schedule_monitoring

POOL = "burbot-monitoring"


def main():
    for flow, name, interval, limit in (
        (process_monitoring, "monitoring-process", None, 4),
        (schedule_monitoring, "monitoring-scheduler", 60, 1),
    ):
        deployment = flow.to_deployment(
            name=name,
            interval=interval,
            concurrency_limit=limit,
            entrypoint_type=EntrypointType.MODULE_PATH,
        )
        print(f"Registered {flow.name}/{name} ({deployment.apply(work_pool_name=POOL)})")


if __name__ == "__main__":
    main()
