"""Background scheduler for periodic subscription syncing and discovery scanning."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from croniter import croniter

from yubal_api.api.exceptions import SubscriptionNotFoundError
from yubal_api.db.subscription import Subscription
from yubal_api.domain.enums import JobSource
from yubal_api.services.discovery_service import DiscoveryService
from yubal_api.services.job_executor import JobExecutor
from yubal_api.services.subscription_service import SubscriptionService
from yubal_api.settings import Settings

logger = logging.getLogger(__name__)


class Scheduler:
    """Background scheduler that syncs subscriptions and runs discovery periodically."""

    def __init__(
        self,
        subscription_service: SubscriptionService,
        job_executor: JobExecutor,
        settings: Settings,
        discovery_service: DiscoveryService | None = None,
    ) -> None:
        """Initialize scheduler."""
        self._subscription_service = subscription_service
        self._job_executor = job_executor
        self._settings = settings
        self._discovery_service = discovery_service
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._next_sync_at: datetime | None = None
        self._next_discovery_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._task is not None and not self._task.done()

    @property
    def enabled(self) -> bool:
        """Check if scheduler is enabled (from settings)."""
        return self._settings.scheduler_enabled

    @property
    def cron_expression(self) -> str:
        """Get cron expression (from settings)."""
        return self._settings.scheduler_cron

    @property
    def next_run_at(self) -> datetime | None:
        """Get next scheduled run time."""
        return self._next_sync_at

    @property
    def next_discovery_run_at(self) -> datetime | None:
        """Get next scheduled discovery run time."""
        return self._next_discovery_at

    def _get_next_run_time(self, cron_expr: str) -> datetime:
        """Calculate next run time using croniter in configured timezone."""
        tz = self._settings.timezone
        cron = croniter(cron_expr, datetime.now(tz))
        next_time = cron.get_next(datetime)
        if next_time.tzinfo is None:
            next_time = next_time.replace(tzinfo=tz)
        return next_time.astimezone(UTC)

    def start(self) -> None:
        """Start the scheduler background task."""
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler background task."""
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._next_sync_at = None
        self._next_discovery_at = None
        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            now = datetime.now(UTC)

            # Calculate next sync time
            next_sync = self._get_next_run_time(self._settings.scheduler_cron)
            self._next_sync_at = next_sync if self._settings.scheduler_enabled else None
            sync_wait = (next_sync - now).total_seconds()

            # Calculate next discovery time
            discovery_enabled = (
                self._settings.discovery_enabled and self._discovery_service is not None
            )
            if discovery_enabled:
                next_discovery = self._get_next_run_time(self._settings.discovery_cron)
                self._next_discovery_at = next_discovery
                discovery_wait = (next_discovery - now).total_seconds()
            else:
                self._next_discovery_at = None
                discovery_wait = float("inf")

            # Wait for the nearest event
            wait_seconds = min(max(0, sync_wait), max(0, discovery_wait))

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=wait_seconds if wait_seconds < float("inf") else 3600,
                )
                break
            except TimeoutError:
                await self._run_due_tasks()

    async def _run_due_tasks(self) -> None:
        """Run all due tasks (sync and discovery)."""
        now = datetime.now(UTC)

        if self._settings.scheduler_enabled:
            next_sync = self._get_next_run_time(self._settings.scheduler_cron)
            if next_sync <= now:
                logger.info("Scheduler: running subscription sync")
                await self._sync_all_enabled()

        if self._settings.discovery_enabled and self._discovery_service is not None:
            next_discovery = self._get_next_run_time(self._settings.discovery_cron)
            if next_discovery <= now:
                logger.info("Scheduler: running discovery scan")
                await asyncio.to_thread(self._discovery_service.run_scan)

    def _create_jobs_for_subscriptions(
        self, subscriptions: list[Subscription]
    ) -> list[str]:
        """Create sync jobs for given subscriptions."""
        job_ids: list[str] = []
        for subscription in subscriptions:
            try:
                job = self._job_executor.create_and_start_job(
                    subscription.url,
                    subscription.max_items,
                    JobSource.SCHEDULER,
                    subscription.id,
                )
                if job is None:
                    logger.warning(
                        "Could not create job for %s (queue full)",
                        subscription.name,
                    )
                    continue

                job_ids.append(job.id)
                self._subscription_service.update(
                    subscription.id,
                    {"last_synced_at": datetime.now(UTC)},
                )
                logger.info(
                    "Created sync job %s for %s",
                    job.id[:8],
                    subscription.name,
                )
            except Exception:
                logger.exception(
                    "Failed to create job for %s",
                    subscription.name,
                )
        return job_ids

    async def _sync_all_enabled(self) -> list[str]:
        """Sync all enabled subscriptions (async wrapper)."""
        return self._create_jobs_for_subscriptions(
            self._subscription_service.list(enabled=True)
        )

    def sync_subscription(self, subscription_id: UUID) -> str | None:
        """Create sync job for a single subscription. Returns job_id or None."""
        try:
            subscription = self._subscription_service.get(subscription_id)
        except SubscriptionNotFoundError:
            return None

        job_ids = self._create_jobs_for_subscriptions([subscription])
        return job_ids[0] if job_ids else None

    def sync_all(self) -> list[str]:
        """Create sync jobs for all enabled subscriptions. Returns job_ids."""
        return self._create_jobs_for_subscriptions(
            self._subscription_service.list(enabled=True)
        )

    def run_discovery(self) -> int:
        """Trigger a discovery scan immediately. Returns new suggestions count."""
        if self._discovery_service is None:
            logger.warning(
                "Discovery scan requested but no discovery service configured"
            )
            return 0
        return self._discovery_service.run_scan()
