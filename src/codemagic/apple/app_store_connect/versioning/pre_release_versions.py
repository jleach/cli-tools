from dataclasses import dataclass
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type

from codemagic.apple.app_store_connect.resource_manager import ResourceManager
from codemagic.apple.resources import Build
from codemagic.apple.resources import PreReleaseVersion
from codemagic.apple.resources import Resource
from codemagic.apple.resources import ResourceId


class PreReleaseVersions(ResourceManager[PreReleaseVersion]):
    """
    Prerelease Versions
    https://developer.apple.com/documentation/appstoreconnectapi/prerelease_versions_and_beta_testers/prerelease_versions
    """

    @property
    def resource_type(self) -> Type[PreReleaseVersion]:
        return PreReleaseVersion

    @dataclass
    class Filter(ResourceManager.Filter):
        app: Optional[ResourceId] = None
        version: Optional[str] = None

    class Include(ResourceManager.Include):
        BUILDS = ('builds', Build)

    def list(self,
             resource_filter: Filter = Filter(),
             include: Include = Include.BUILDS) -> Tuple[List[PreReleaseVersion], List[Resource]]:
        """
        https://developer.apple.com/documentation/appstoreconnectapi/list_prerelease_versions
        """

        params = {
            'include': include.include_name,
            **resource_filter.as_query_params(),
        }
        results = self.client.paginate_with_included(f'{self.client.API_URL}/preReleaseVersions', params=params)
        return (
            [PreReleaseVersion(prerelease_version) for prerelease_version in results.data],
            [include.resource_type(included) for included in results.included]
        )
