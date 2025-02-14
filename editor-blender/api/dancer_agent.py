import asyncio
from dataclasses import dataclass
from typing import Optional

from ..client import client
from ..core.models import DancersArray
from ..core.utils.convert import dancers_query_to_state
from ..graphqls.queries import (
    GET_DANCERS,
    QueryDancersPayload,
    QueryPartOrderByWithRelationInput,
)


@dataclass
class DancerAgent:
    async def get_dancers(self) -> Optional[DancersArray]:
        try:
            response = await client.execute(
                QueryDancersPayload,
                GET_DANCERS,
                variables={"orderBy": [QueryPartOrderByWithRelationInput(id="asc")]},
            )
            dancers = response["dancers"]

            return dancers_query_to_state(dancers)

        except asyncio.CancelledError:
            pass

        except Exception as e:
            print(e)

        return None


dancer_agent = DancerAgent()
