from uoft_aruba import Settings

def test_blmgr_blacklist():
    s = Settings.from_cache()

    mm = s.mm_api_connection
    md1 = s.md_api_connections[0]
    md2 = s.md_api_connections[1]

    try:
        mm.login()
        md1.login()
        md2.login()
        mm.wlan.blmgr_blacklist_add("11:11:11:11:11:11")
        blacklist = [x["STA"] for x in md1.wlan.get_ap_client_blacklist()]
        blacklist += [x["STA"] for x in md2.wlan.get_ap_client_blacklist()]
        blacklist = list(set(blacklist))
        assert "11:11:11:11:11:11" in blacklist
        mm.wlan.blmgr_blacklist_remove("11:11:11:11:11:11")
        blacklist = [x["STA"] for x in md1.wlan.get_ap_client_blacklist()]
        blacklist += [x["STA"] for x in md2.wlan.get_ap_client_blacklist()]
        blacklist = list(set(blacklist))
        assert "11:11:11:11:11:11" not in blacklist
    finally:
        mm.logout()
        md1.logout()
        md2.logout()

