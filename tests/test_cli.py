from mcp_anything.cli import parse_args


def test_parse_args_supports_capability_profiles():
    config = parse_args(
        [
            "--allow-writes",
            "--tags",
            "Client,Deal",
            "--operations",
            "listClients,getClient",
            "--deny-operations",
            "deleteClient",
        ]
    )

    assert config["allow_writes"] is True
    assert config["allowed_tags"] == {"Client", "Deal"}
    assert config["allowed_operations"] == {"listClients", "getClient"}
    assert config["denied_operations"] == {"deleteClient"}
