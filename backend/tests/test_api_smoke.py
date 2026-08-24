from fastapi.testclient import TestClient

from personal_affairs.config import get_settings


def test_health_and_openapi_do_not_require_database(monkeypatch) -> None:
    monkeypatch.setenv("PERSONAL_AFFAIRS_APP_ENV", "unit")
    get_settings.cache_clear()
    from personal_affairs.api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        schema = client.get("/api/v1/openapi.json").json()
        assert schema["info"]["title"] == "Personal Affairs API"
        assert "/api/v1/items" in schema["paths"]
        reminder_path = schema["paths"]["/api/v1/items/{item_id}/reminder"]
        assert "get" in reminder_path
        assert "put" in reminder_path
        assert "delete" in reminder_path
        deliveries_params = schema["paths"]["/api/v1/reminders/deliveries"]["get"]["parameters"]
        param_names = {param["name"] for param in deliveries_params}
        assert {"limit", "channel", "status", "unseen"} <= param_names
        assert "post" in schema["paths"]["/api/v1/reminders/deliveries/{delivery_id}/ack"]
        assert "post" in schema["paths"]["/api/v1/reminders/deliveries/{delivery_id}/snooze"]
        assert "post" in schema["paths"]["/api/v1/reminders/deliveries/{delivery_id}/retry"]
        assert "get" in schema["paths"]["/api/v1/reminders/channels"]
        assert "get" in schema["paths"]["/api/v1/push/vapid-key"]
        subscriptions = schema["paths"]["/api/v1/push/subscriptions"]
        assert "post" in subscriptions
        assert "delete" in subscriptions
        items_params = schema["paths"]["/api/v1/items"]["get"]["parameters"]
        items_param_names = {param["name"] for param in items_params}
        assert {"scope", "include_archived", "search"} <= items_param_names
        assert "get" in schema["paths"]["/api/v1/export"]
        items_id_path = schema["paths"]["/api/v1/items/{item_id}"]
        assert "delete" in items_id_path
        assert "post" in schema["paths"]["/api/v1/items/{item_id}/restore-deleted"]
        assert "delete" in schema["paths"]["/api/v1/items/{item_id}/purge"]
        assert "deleted" in items_param_names
        milestone_path = schema["paths"]["/api/v1/projects/{project_id}/milestones/{milestone_id}"]
        assert "patch" in milestone_path
        assert "delete" in milestone_path
        tags_path = schema["paths"]["/api/v1/tags"]
        assert "get" in tags_path
        assert "post" in tags_path
        assert "patch" in schema["paths"]["/api/v1/tags/{tag_id}"]
        assert "delete" in schema["paths"]["/api/v1/tags/{tag_id}"]
        tag_items_params = schema["paths"]["/api/v1/tags/{tag_id}/items"]["get"]["parameters"]
        tag_param_names = {param["name"] for param in tag_items_params}
        assert {"include_done", "scope", "recursive"} <= tag_param_names
        people_path = schema["paths"]["/api/v1/people"]
        assert "get" in people_path
        assert "post" in people_path
        assert "patch" in schema["paths"]["/api/v1/people/{person_id}"]
        assert "delete" in schema["paths"]["/api/v1/people/{person_id}"]
        groups_path = schema["paths"]["/api/v1/project-groups"]
        assert "get" in groups_path
        assert "post" in groups_path
        assert "patch" in schema["paths"]["/api/v1/project-groups/{group_id}"]
        assert "post" in schema["paths"]["/api/v1/project-groups/{group_id}/archive"]
        assert "post" in schema["paths"]["/api/v1/project-groups/{group_id}/restore"]
        group_out = schema["components"]["schemas"]["ProjectGroupOut"]["properties"]
        assert {"project_count", "risk_count", "sort_order", "archived_at"} <= set(group_out)
        project_out = schema["components"]["schemas"]["ProjectOut"]["properties"]
        assert {"group_id", "group_name"} <= set(project_out)
        project_create = schema["components"]["schemas"]["ProjectCreate"]["properties"]
        assert "group_id" in project_create
        tag_out = schema["components"]["schemas"]["TagOut"]["properties"]
        assert "pinned" in tag_out
        prefs_out = schema["components"]["schemas"]["PreferencesOut"]["properties"]
        assert "identity_scope_rules" in prefs_out
        assert "post" in schema["paths"]["/api/v1/items/{item_id}/focus/start"]
        assert "post" in schema["paths"]["/api/v1/items/{item_id}/focus/stop"]
        assert "get" in schema["paths"]["/api/v1/focus/active"]
        assert "get" in schema["paths"]["/api/v1/focus/today"]
        focus_out = schema["components"]["schemas"]["FocusSessionOut"]["properties"]
        assert {"item_title", "started_at", "duration_seconds"} <= set(focus_out)
        assert "post" in schema["paths"]["/api/v1/items/{item_id}/checkin"]
        assert "get" in schema["paths"]["/api/v1/habits/week"]
        assert "get" in schema["paths"]["/api/v1/focus/week"]
        views_path = schema["paths"]["/api/v1/saved-views"]
        assert "get" in views_path
        assert "post" in views_path
        assert "patch" in schema["paths"]["/api/v1/saved-views/{view_id}"]
        assert "delete" in schema["paths"]["/api/v1/saved-views/{view_id}"]
        assert "get" in schema["paths"]["/api/v1/calendar/feed.ics"]
        assert "post" in schema["paths"]["/api/v1/calendar/feed-token"]
        tokens_path = schema["paths"]["/api/v1/auth/tokens"]
        assert "post" in tokens_path
        assert "get" in tokens_path
        assert "delete" in schema["paths"]["/api/v1/auth/tokens/{token_id}"]
        token_create = schema["components"]["schemas"]["TokenCreate"]["properties"]
        assert {"name", "scopes", "expires_in_days"} <= set(token_create)
        token_created = schema["components"]["schemas"]["TokenCreated"]["properties"]
        assert {"name", "scopes", "token", "created_at"} <= set(token_created)
        webhooks_path = schema["paths"]["/api/v1/webhooks"]
        assert "get" in webhooks_path
        assert "post" in webhooks_path
        assert "delete" in schema["paths"]["/api/v1/webhooks/{webhook_id}"]
        assert "get" in schema["paths"]["/api/v1/webhooks/events"]
        webhook_create = schema["components"]["schemas"]["WebhookCreate"]["properties"]
        assert {"name", "url", "events"} <= set(webhook_create)
        webhook_created = schema["components"]["schemas"]["WebhookCreated"]["properties"]
        assert {"secret", "events", "active"} <= set(webhook_created)
        webhook_event = schema["components"]["schemas"]["WebhookEventOut"]["properties"]
        assert {"event_type", "status", "attempt_count"} <= set(webhook_event)
        proposals_path = schema["paths"]["/api/v1/agent-proposals"]
        assert "get" in proposals_path
        assert "post" in proposals_path
        proposal_id_path = schema["paths"]["/api/v1/agent-proposals/{proposal_id}"]
        assert "get" in proposal_id_path
        assert "post" in schema["paths"]["/api/v1/agent-proposals/{proposal_id}/approve"]
        assert "post" in schema["paths"]["/api/v1/agent-proposals/{proposal_id}/reject"]
        assert "post" in schema["paths"]["/api/v1/agent-proposals/{proposal_id}/ignore"]
        proposal_out = schema["components"]["schemas"]["AgentProposalOut"]["properties"]
        assert {"state", "risk_tier", "proposed_payload", "applied_item_id"} <= set(proposal_out)
        assert "post" in schema["paths"]["/api/v1/integrations/feishu/im/events"]
