from uuid import UUID

from personal_affairs.api.schemas import ReminderPut
from personal_affairs.config import Settings
from personal_affairs.domain.enums import DeliveryChannel, ReminderTiming
from personal_affairs.domain.models import ItemSchedule
from personal_affairs.domain.reminder_state import calculate_reminder_schedule
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository


class ReminderService:
    def __init__(self, reminders: RemindersRepository, items: ItemsRepository, settings: Settings):
        self.reminders = reminders
        self.items = items
        self.settings = settings

    def upsert(self, user_id: UUID, item_id: UUID, request: ReminderPut) -> dict:
        reminder = self.reminders.upsert_for_item(user_id, item_id, request.model_dump())
        self.reconcile(user_id, item_id)
        return reminder

    def reconcile(self, user_id: UUID, item_id: UUID) -> None:
        item = self.items.get_item(user_id, item_id)
        reminder = self.reminders.get_active_for_item(user_id, item_id)
        if not item or not reminder:
            return
        if item["status"] in {"done", "cancelled"} or item["archived_at"] is not None:
            self.items.cancel_pending_deliveries(user_id, item_id)
            return
        schedule = ItemSchedule(
            all_day=item["all_day"],
            start_at=item["start_at"],
            due_at=item["due_at"],
            start_date=item["start_date"],
            due_date=item["due_date"],
        )
        scheduled_for = calculate_reminder_schedule(
            schedule,
            ReminderTiming(reminder["timing"]),
            reminder["offset_minutes"],
            reminder["timezone"],
        )
        channels = [DeliveryChannel.IN_APP]
        if reminder["external_enabled"] and self.settings.feishu_webhook_url:
            channels.append(DeliveryChannel.FEISHU)
        if reminder["external_enabled"] and self.settings.ntfy_topic_url:
            channels.append(DeliveryChannel.NTFY)
        self.reminders.replace_pending_deliveries(
            user_id, reminder["id"], item_id, scheduled_for, channels
        )
