from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import PersonCreate, PersonOut, PersonPatch
from personal_affairs.application.people_service import PeopleService
from personal_affairs.storage.repositories.people import PeopleRepository

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(
    include_inactive: bool = Query(True),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return PeopleRepository(conn).list_people(user_id, include_inactive)


@router.post("", response_model=PersonOut, dependencies=[Depends(require_csrf)])
def create_person(
    request: PersonCreate,
    response: Response,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    person = PeopleService(PeopleRepository(conn)).create(user_id, request.name, request.identity, request.note)
    response.status_code = 201
    return person


@router.patch("/{person_id}", response_model=PersonOut, dependencies=[Depends(require_csrf)])
def patch_person(
    person_id: UUID,
    request: PersonPatch,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    person = PeopleService(PeopleRepository(conn)).patch(user_id, person_id, request.model_dump(exclude_unset=True))
    if not person:
        return not_found()
    return person


@router.delete("/{person_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_person(
    person_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    if not PeopleRepository(conn).delete(user_id, person_id):
        return not_found()
    return Response(status_code=204)
