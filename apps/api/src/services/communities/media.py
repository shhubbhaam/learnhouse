from fastapi import HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.communities.communities import Community
from src.db.organizations import Organization
from src.db.users import PublicUser
from src.security.rbac import (
    AccessAction,
    authorization_verify_if_user_is_anon,
    check_resource_access,
)
from src.services.communities.moderation import get_community_settings
from src.services.utils.upload_content import upload_file

# Images posted in discussions and replies. Kept below the generic 15 MB image
# cap since these are inline chat attachments, not course assets.
COMMUNITY_MEDIA_MAX_SIZE = 10 * 1024 * 1024


class CommunityMediaUploadResponse(BaseModel):
    file_id: str
    org_uuid: str
    community_uuid: str


async def upload_community_media(
    request: Request,
    community_uuid: str,
    media_file: UploadFile,
    current_user: PublicUser,
    db_session: AsyncSession,
) -> CommunityMediaUploadResponse:
    """
    Upload an image for use inside a discussion or reply.

    Anyone who can read (and therefore post in) the community may upload,
    unless the community has turned ``allow_images`` off. The returned ids are
    what the client puts in a ``communityImage`` content node.
    """
    await authorization_verify_if_user_is_anon(current_user.id)

    community = (
        await db_session.execute(
            select(Community).where(Community.community_uuid == community_uuid)
        )
    ).scalars().first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    await check_resource_access(
        request, db_session, current_user, community.community_uuid, AccessAction.READ
    )

    settings = get_community_settings(community)
    if not bool(settings.get("allow_images", True)):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Images are not allowed in this community.",
                "code": "MODERATION_IMAGES_DISABLED",
            },
        )

    org = (
        await db_session.execute(
            select(Organization).where(Organization.id == community.org_id)
        )
    ).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    file_id = await upload_file(
        file=media_file,
        directory=f"communities/{community.community_uuid}/media",
        type_of_dir="orgs",
        uuid=org.org_uuid,
        allowed_types=["image"],
        filename_prefix="media",
        max_size=COMMUNITY_MEDIA_MAX_SIZE,
    )

    return CommunityMediaUploadResponse(
        file_id=file_id,
        org_uuid=org.org_uuid,
        community_uuid=community.community_uuid,
    )
