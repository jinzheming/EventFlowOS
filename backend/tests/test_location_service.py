import httpx

from personal_affairs.application.location_service import AMapClient
from personal_affairs.config import Settings


def test_amap_resolves_poi_and_route_with_server_side_key() -> None:
    responses = {
        "/v3/place/text": {"status": "1", "pois": [{"id": "B1", "name": "测试大厦", "address": "上海市测试路 1 号", "location": "121.5000,31.2000", "cityname": "上海"}]},
        "/v5/direction/driving": {"status": "1", "route": {"paths": [{"distance": "1200", "duration": "600"}]}},
    }

    def get(url: str, **_: object) -> httpx.Response:
        path = url.removeprefix("https://restapi.amap.com")
        return httpx.Response(200, json=responses[path], request=httpx.Request("GET", url))

    client = AMapClient(Settings(amap_enabled=True, amap_key="secret"), getter=get)
    resolved = client.search_poi("测试大厦", city="上海")
    assert resolved["candidates"][0]["poi_id"] == "B1"
    route = client.route((121.49, 31.2), (121.5, 31.2), "driving")
    assert route is not None
    assert route.duration_seconds == 600


def test_amap_is_explicitly_disabled_without_key() -> None:
    result = AMapClient(Settings()).resolve("任意地址")
    assert result == {"status": "disabled", "provider": "amap", "candidates": []}
