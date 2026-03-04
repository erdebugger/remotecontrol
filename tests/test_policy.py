import unittest

from remotecontrol.policy import InternetPolicy


class InternetPolicyTests(unittest.TestCase):
    def test_policy_block_all_script_contains_block_rule(self):
        policy = InternetPolicy(mode="block_all")
        script = policy.to_powershell()
        self.assertIn("RCA-Block-All-Out", script)

    def test_policy_allow_list_requires_entries(self):
        policy = InternetPolicy(mode="allow_list")
        with self.assertRaises(ValueError):
            policy.to_powershell()

    def test_policy_allow_list_contains_domains_and_ips(self):
        policy = InternetPolicy(
            mode="allow_list",
            allowed_domains=["*.example.com"],
            allowed_ips=["10.0.0.10"],
            allowed_dns_servers=["1.1.1.1"],
        )
        script = policy.to_powershell()
        self.assertIn("RemoteFqdn *.example.com", script)
        self.assertIn("RemoteAddress 10.0.0.10", script)
        self.assertIn("RemotePort 53", script)


if __name__ == "__main__":
    unittest.main()
