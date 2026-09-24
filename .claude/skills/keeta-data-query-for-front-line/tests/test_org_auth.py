import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts" / "capability1_standard"
sys.path.insert(0, str(SCRIPT_DIR))

import org_auth  # noqa: E402


class CheckQueryPermissionTest(unittest.TestCase):
    def test_allows_permitted_org_value_when_node_flag_is_false(self):
        with (
            patch.object(org_auth, "list_org_lines", return_value=[{"bizType": 1148702721}]),
            patch.object(
                org_auth,
                "list_org_nodes",
                return_value=[
                    {
                        "orgNodeType": 10270831,
                        "orgNodeName": "四级组织架构负责人_鉴权",
                        "hasPermission": False,
                    }
                ],
            ),
            patch.object(
                org_auth,
                "list_org_node_values",
                return_value=[
                    {
                        "orgId": "1369_jiwei02_jiwei02_elsayedmetwaly",
                        "orgName": "Elsayed Metwaly",
                        "hasPermission": True,
                    }
                ],
            ),
        ):
            allowed, reason = org_auth.check_query_permission(
                biz_type=1148702721,
                org_node_type=10270831,
                org_ids=["1369_jiwei02_jiwei02_elsayedmetwaly"],
                source=1,
            )

        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_denies_unpermitted_org_value(self):
        with (
            patch.object(org_auth, "list_org_lines", return_value=[{"bizType": 1148702721}]),
            patch.object(
                org_auth,
                "list_org_nodes",
                return_value=[{"orgNodeType": 10270831, "hasPermission": False}],
            ),
            patch.object(
                org_auth,
                "list_org_node_values",
                return_value=[{"orgId": "other_org", "hasPermission": True}],
            ),
        ):
            allowed, reason = org_auth.check_query_permission(
                biz_type=1148702721,
                org_node_type=10270831,
                org_ids=["denied_org"],
                source=1,
            )

        self.assertFalse(allowed)
        self.assertIn("denied_org", reason)


if __name__ == "__main__":
    unittest.main()
