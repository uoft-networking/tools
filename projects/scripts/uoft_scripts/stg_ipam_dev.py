"""
Code for pulling data out of the uoft-ipam database's dev instance
"""

import sys
import contextlib
import typing as t
from datetime import date
from ipaddress import IPv4Network, IPv6Network
from time import monotonic_ns

from uoft_core import BaseSettings, SecretStr
from uoft_core import logging

from sqlmodel import Field, SQLModel, Session, create_engine, select
import sqlalchemy as sa
import typer

from .nautobot import get_settings, Record

logger = logging.getLogger(__name__)

DEBUG_MODE = False


class Settings(BaseSettings):
    user: str
    password: SecretStr
    host: str = "ipam-dev.its.utoronto.ca"
    port: int = 5432
    database: str = "ipam"
    tags_by_network: dict[IPv4Network | IPv6Network, str] = Field(
        default_factory=dict,
        title="Tags by Network",
        description="A mapping of network prefixes to tags. "
        "The key is the network prefix, and the value is the tag to apply to networks that fall within that prefix.",
    )
    tags_by_network_exact: dict[IPv4Network | IPv6Network, str] = Field(
        default_factory=dict,
        title="Tags by Network",
        description="A mapping of network prefixes to tags. "
        "The key is the network prefix, and the value is the tag to apply to the network that exactly matches that prefix.",
    )

    class Config(BaseSettings.Config):
        app_name = "stg-ipam-dev"

    def get_dsn(self) -> str:
        auth = f"{self.user}:{self.password.get_secret_value()}"
        return f"postgresql+psycopg://{auth}@{self.host}:{self.port}/{self.database}"


NetworkType = t.Literal[
    "VoIP"
    "L2-Data"
    "L3-Data"
    "Wireless"
    "EClass"
    "FS"
    "OBM"
    "Other"
    "NAAS"
    "Core"
    "User"
    "Printer"
    "Untrusted"
    "CDE-POS"
    "Server Public"
    "Server Production"
    "Server Non-Production"
    "Utilities"
    "Management"
    "Podium"
    "AS239"
]

UserType = t.Literal["UTORid", "Group", "External", "Admin", "Tech"]


class User(SQLModel, table=True):
    __tablename__ = "users"  # type: ignore

    username: str = Field(primary_key=True)
    name: str
    email: str | None = None
    type: UserType = Field(sa_type=sa.String)
    reg_date: date = Field(default=date.today)


class Org(SQLModel, table=True):
    __tablename__ = "orgs"  # type: ignore

    id: int = Field(primary_key=True)
    name: str | None = None
    org: str | None = None
    hrid: int | None = None


class Network(SQLModel, table=True):
    __tablename__ = "networks"  # type: ignore

    id: int = Field(primary_key=True)
    ip4: IPv4Network | None = None
    ip6: IPv6Network | None = None
    vlan_ref: int | None = Field(default=None, foreign_key="vlans.id")
    vrf_ref: int | None = Field(default=None, foreign_key="vrfs.id")
    net_type: NetworkType = Field(sa_type=sa.String)
    name: str
    location: str
    description: str
    comments: str | None = None
    adminc: str | None = Field(default=None, foreign_key="users.username")
    techc: str | None = Field(default=None, foreign_key="users.username")
    adminc_alt: str | None = Field(default=None, foreign_key="users.username")
    techc_alt: str | None = Field(default=None, foreign_key="users.username")
    last_update: date = Field(default=date.today)
    org: int | None = Field(default=None, foreign_key="orgs.id")
    priority: int = 8
    vxlan_ref: int | None = Field(default=None, foreign_key="vxlans.id")
    _parent: int | None = None

    def __setattr__(self, key, value):
        if key == "_parent":
            self.__dict__["_parent"] = value
        else:
            super().__setattr__(key, value)


@contextlib.contextmanager
def session():
    settings = Settings.from_cache()
    engine = create_engine(settings.get_dsn())
    with Session(engine) as session:
        yield session


#####################################################################
## Why do we select all records from all the tables we care about  ##
## instead of asking the database to join and return only the data ##
## we need? because it's faster! In testing, doing a proper JOIN   ##
## on all related tables took 20 seconds to complete, but asking   ##
## the postgres server to just serialize and send all these tables ##
## takes only 0.5 to 1.5 seconds!!!                                ##
#####################################################################


class Data:
    def __init__(self, networks: dict[int, Network], users: dict[str, User], orgs: dict[int, Org]):
        self.networks = networks
        self.users = users
        self.orgs = orgs

    def __repr__(self):
        return f"Data(networks={len(self.networks)}, users={len(self.users)}, orgs={len(self.orgs)})"


def _calculate_parentage(networks: dict[int, Network]) -> dict[int, Network]:
    v4_networks = sorted(
        [n for n in networks.values() if n.ip4],
        key=lambda x: int(x.ip4.netmask),  # type: ignore
        reverse=True,
    )

    for network in v4_networks:
        next_index = v4_networks.index(network) + 1
        for n in v4_networks[next_index:]:
            if n.ip4.supernet_of(network.ip4):  # type: ignore
                network._parent = n.id
                break

    v6_networks = sorted(
        [n for n in networks.values() if n.ip6],
        key=lambda x: int(x.ip6.netmask),  # type: ignore
        reverse=True,
    )

    # theoretically, we could have a network that has a v4 parent and a v6 parent
    # but we're not going to worry about that for now. it's likely to be a very rare
    # edge case for the forseeable future
    for network in v6_networks:
        next_index = v6_networks.index(network) + 1
        for n in v6_networks[next_index:]:
            if n.ip6.supernet_of(network.ip6):  # type: ignore
                network._parent = n.id
                break

    return networks


def get_data():
    with session() as s:
        logger.info("Fetching data from uoft-ipam-dev")
        start = monotonic_ns()
        networks = {}
        for network in s.exec(select(Network)):
            # print(f'fetched {network.name}')
            networks[network.id] = network
        logger.debug(f"Fetched {len(networks)} networks")
        users = {}
        for user in s.exec(select(User)):
            # print(f'fetched {user.name}')
            users[user.username] = user
        logger.debug(f"Fetched {len(users)} users")
        orgs = {}
        for org in s.exec(select(Org)):
            # print(f'fetched {org.name}')
            orgs[org.id] = org
        logger.info(f"Time taken: {(monotonic_ns() - start) / 1e6:.2f}ms")
    return Data(networks=networks, users=users, orgs=orgs)


app = typer.Typer(
    name="stg-ipam-dev",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback():
    pass


@app.command()
def sync_to_nautobot():
    """Syncronize networks and contacts from the database behind ipam.utoronto.ca into nautobot"""

    nb = get_settings(dev=True).api_connection()

    data = get_data()

    logger.info("Syncing networks...")

    # will need this when syncing contacts
    contacts_to_sync: dict[str, User] = {}

    # sync networks
    utsg_rir = nb.ipam.rirs.get(name="UTSG")
    assert isinstance(utsg_rir, Record), "UTSG RIR not found in Nautobot"
    logger.info("Loading existing prefixes from Nautobot...")
    nb_prefixes = {p.prefix: p for p in nb.ipam.prefixes.all()}  # type: ignore
    to_create = []
    to_update = []

    def _create_or_update(pfx, net):
        stg_name = net.name
        org_code = data.orgs[net.org].org
        stg_desc = net.description
        stg_comments = net.comments
        stg_net_type = net.net_type
        if pfx in nb_prefixes:
            nb_obj = nb_prefixes[pfx]
            nb_stg_name = nb_obj.description  # type: ignore
            nb_org_code = nb_obj.custom_fields.get("org_code")  # type: ignore
            nb_extra = nb_obj.custom_fields.get("extra") or {}  # type: ignore
            nb_stg_desc = nb_extra.get("stg_desc")
            nb_stg_comments = nb_extra.get("stg_comments")
            nb_stg_net_type = nb_extra.get("stg_net_type")
            if dict(
                stg_name=stg_name,
                org_code=org_code,
                stg_desc=stg_desc,
                stg_comments=stg_comments,
                stg_net_type=stg_net_type,
            ) != dict(
                stg_name=nb_stg_name,
                org_code=nb_org_code,
                stg_desc=nb_stg_desc,
                stg_comments=nb_stg_comments,
                stg_net_type=nb_stg_net_type,
            ):
                to_update.append(
                    dict(
                        id=nb_obj.id,  # type: ignore
                        description=stg_name,
                        custom_fields=dict(
                            org_code=org_code,
                            extra=dict(stg_desc=stg_desc, stg_comments=stg_comments, stg_net_type=stg_net_type),
                        ),
                    )
                )
            else:
                logger.info(f"Prefix {pfx} already up to date in Nautobot")
        else:
            to_create.append(
                dict(
                    prefix=pfx,
                    rir=utsg_rir.id,
                    status="Active",
                    description=net.name,
                    type="container",
                    custom_fields=dict(
                        org_code=org_code,
                        extra=dict(stg_desc=stg_desc, stg_comments=stg_comments, stg_net_type=stg_net_type),
                    ),
                )
            )

    for net in data.networks.values():
        if "utsc-" not in net.name:
            continue
        assert net.org is not None
        if net.ip4:
            _create_or_update(str(net.ip4), net)
        if net.ip6:
            _create_or_update(str(net.ip6), net)

        for attr in ["techc", "techc_alt", "adminc", "adminc_alt"]:
            if (uid := getattr(net, attr)) and uid not in contacts_to_sync:
                contacts_to_sync[uid] = data.users[uid]

    logger.info(f"Creating {len(to_create)} new prefixes...")
    nb.ipam.prefixes.create(to_create)

    logger.info(f"Updating {len(to_update)} existing prefixes...")
    nb.ipam.prefixes.update(to_update)

    # sync contacts
    logger.info("Syncing organizations...")
    nb_contacts = {t.name: t for t in nb.extras.contacts.all()}  # type: ignore
    nb_teams = {t.name: t for t in nb.extras.teams.all()}  # type: ignore
    contacts_to_create = []
    contacts_to_update = []
    teams_to_create = []
    teams_to_update = []
    for user_id, user in contacts_to_sync.items():
        if user.type == "UTORid":
            if user.name in nb_contacts:
                nb_obj = nb_contacts[user.name]
                if nb_obj.email != user.email:  # type: ignore
                    contacts_to_update.append(
                        dict(
                            id=nb_obj.id,  # type: ignore
                            email=user.email,
                            custom_fields=dict(extras=dict(stg_ipam_id=user_id)),
                        )
                    )
            else:
                contacts_to_create.append(
                    dict(name=user.name, email=user.email, custom_fields=dict(extras=dict(stg_ipam_id=user_id)))
                )
        elif user.type == "Group":
            if user.name in nb_teams:
                nb_obj = nb_teams[user.name]
                if nb_obj.email != user.email:  # type: ignore
                    teams_to_update.append(
                        dict(
                            id=nb_obj.id,  # type: ignore
                            email=user.email,
                            custom_fields=dict(extras=dict(stg_ipam_id=user_id)),
                        )
                    )
            else:
                teams_to_create.append(
                    dict(name=user.name, email=user.email, custom_fields=dict(extras=dict(stg_ipam_id=user_id)))
                )
        else:
            logger.error(f"Not sure how to handle user type {user.type} (user_id: {user_id})")
    logger.info(f"Creating {len(contacts_to_create)} new contacts...")
    nb.extras.contacts.create(contacts_to_create)
    logger.info(f"Updating {len(contacts_to_update)} existing contacts...")
    nb.extras.contacts.update(contacts_to_update)
    logger.info(f"Creating {len(teams_to_create)} new teams...")
    nb.extras.teams.create(teams_to_create)
    logger.info(f"Updating {len(teams_to_update)} existing teams...")
    nb.extras.teams.update(teams_to_update)

    # Associate contacts / teams to prefixes
    logger.debug("Refreshing contacts and teams cache...")
    nb_contacts = {t.name: t for t in nb.extras.contacts.all()}  # type: ignore
    nb_teams = {t.name: t for t in nb.extras.teams.all()}  # type: ignore
    logger.debug("Refreshing prefixes cache...")
    nb_prefixes = {p.prefix: p for p in nb.ipam.prefixes.all()}  # type: ignore
    logger.info("Associating contacts and teams with prefixes...")

    existing_associations = nb.extras.contact_associations.filter(associated_object_type="ipam.prefix")
    to_create = []
    to_update = []

    def _existing_association(pfx_id, contact=None, team=None):
        assert contact or team
        for assoc in existing_associations:
            if assoc.associated_object_id == pfx_id:  # type: ignore
                if contact and assoc.contact and assoc.contact.id == contact:  # type: ignore
                    return assoc.id  # type: ignore
                if team and assoc.team and assoc.team.id == team:  # type: ignore
                    return assoc.id  # type: ignore

    for net in data.networks.values():
        if "utsc-" not in net.name:
            continue
        pfxs = []
        teams = []
        contacts = []
        if net.ip4:
            pfxs.append(nb_prefixes[str(net.ip4)])
        if net.ip6:
            pfxs.append(nb_prefixes[str(net.ip6)])

        if net.techc:
            if data.users[net.techc].type == "UTORid":
                contacts.append((nb_contacts[data.users[net.techc].name].id, "Support", "Primary"))  # type: ignore
            elif data.users[net.techc].type == "Group":
                teams.append((nb_teams[data.users[net.techc].name].id, "Support", "Primary"))  # type: ignore
        if net.techc_alt:
            if data.users[net.techc_alt].type == "UTORid":
                contacts.append((nb_contacts[data.users[net.techc_alt].name].id, "Support", "Secondary"))  # type: ignore
            elif data.users[net.techc_alt].type == "Group":
                teams.append((nb_teams[data.users[net.techc_alt].name].id, "Support", "Secondary"))  # type: ignore
        if net.adminc:
            if data.users[net.adminc].type == "UTORid":
                contacts.append((nb_contacts[data.users[net.adminc].name].id, "Administrative", "Primary"))  # type: ignore
            elif data.users[net.adminc].type == "Group":
                teams.append((nb_teams[data.users[net.adminc].name].id, "Administrative", "Primary"))  # type: ignore
        if net.adminc_alt:
            if data.users[net.adminc_alt].type == "UTORid":
                contacts.append((nb_contacts[data.users[net.adminc_alt].name].id, "Administrative", "Secondary"))  # type: ignore
            elif data.users[net.adminc_alt].type == "Group":
                teams.append((nb_teams[data.users[net.adminc_alt].name].id, "Administrative", "Secondary"))  # type: ignore
        for pfx in pfxs:
            for team, role, status in teams:
                if assoc_id := _existing_association(pfx.id, team=team):
                    to_update.append(dict(id=assoc_id, role=dict(name=role), status=dict(name=status)))
                else:
                    to_create.append(
                        dict(
                            associated_object_type="ipam.prefix",
                            associated_object_id=pfx.id,
                            team=team,
                            role=dict(name=role),
                            status=dict(name=status),
                        )
                    )
            for contact, role, status in contacts:
                if assoc_id := _existing_association(pfx.id, contact=contact):
                    to_update.append(dict(id=assoc_id, role=dict(name=role), status=dict(name=status)))
                else:
                    to_create.append(
                        dict(
                            associated_object_type="ipam.prefix",
                            associated_object_id=pfx.id,
                            contact=contact,
                            role=dict(name=role),
                            status=dict(name=status),
                        )
                    )

    logger.info(f"Creating {len(to_create)} new associations...")
    nb.extras.contact_associations.create(to_create)
    # TODO: figure out what this api endpoint actually WANTS from us for updating
    # logger.info(f"Updating {len(to_update)} existing associations...")
    # nb.extras.contact_associations.update(to_update)

    logger.success("Done!")


@app.command()
def sync_to_paloalto(commit: bool = typer.Option(False, help="Commit changes to the Palo Alto API")):
    from uoft_paloalto import Settings as PaloAltoSettings

    s = Settings.from_cache()
    pa = PaloAltoSettings.from_cache().get_api_connection()

    # PaloAlto tech support claims that making API requests one at a time to a single rest api server
    # may be "causing too much load", and ask us to split the requests across multiple servers
    # so we're going to do that here temporarily, in order to demonstrate no performance difference
    from uoft_paloalto.api import API

    pas = PaloAltoSettings.from_cache()
    pa2 = API(
        "https://pa-nsm-2.is.utoronto.ca",
        pas.username,
        pas.password,
        pas.api_key,
        pas.device_group,
        pas.create_missing_tags,
        False,
    )

    data = get_data()

    pa.login()
    pa2.login()
    pa_networks = [
        n
        for n in pa.network_list()
        if n.get("tag")
        and ("source:ipam.utoronto.ca" in n["tag"]["member"])
        and ("net_type:deleted" not in n["tag"]["member"])
    ]
    pa_networks_by_name = {n["@name"]: n for n in pa_networks}
    pa_networks_by_prefix = {n["ip-netmask"]: n for n in pa_networks}

    def derive_tags(net: Network, v: t.Literal[4, 6]) -> set[str]:
        tags = {"source:ipam.utoronto.ca", f"net_type:{net.net_type.replace(' ', '_').lower()}"}
        if net.org:
            tags.add(f"org:{data.orgs[net.org].org}")

        if v == 4:
            tags.add("ip_version:ipv4")

            ip = net.ip4
        else:
            tags.add("ip_version:ipv6")
            ip = net.ip6

        assert ip is not None

        for prefix, tag in s.tags_by_network.items():
            if prefix.version == ip.version and ip.subnet_of(prefix):  # type: ignore
                tags.add(tag)

        for prefix, tag in s.tags_by_network_exact.items():
            if prefix.version == ip.version and ip == prefix:
                tags.add(tag)

        if not ip.is_private and "address_space:cgnat" not in tags:
            tags.add("address_space:public")

        assert len([t for t in tags if t.startswith("address_space:")]) < 2

        if len([t for t in tags if t.startswith("campus:")]) == 0:
            if net.name.startswith("utsg-"):
                tags.add("campus:utsg")
            elif net.name.startswith("utsc-"):
                tags.add("campus:utsc")
            elif net.name.startswith("utm-"):
                tags.add("campus:utm")

        if len([t for t in tags if t.startswith("assigned_by:")]) == 0:
            tags.add("assigned_by:UofT")

        return tags

    def normalize_name(name: str) -> str:
        assert "\t" not in name, f"ipam DB record {name} contains a backslash"
        return name.replace(" ", "-").replace("/", "-").lower()

    def create_or_update(name: str, net: Network, v: t.Literal[4, 6]):
        ip = str(net.ip4) if v == 4 else str(net.ip6)
        tags = derive_tags(net, v)
        if ip in pa_networks_by_prefix or name in pa_networks_by_name:
            if ip in pa_networks_by_prefix:
                pa_obj = pa_networks_by_prefix[ip]
            else:
                pa_obj = pa_networks_by_name[name]

            pa_desc = pa_obj.get("description", "")
            pa_tags = set(pa_obj.get("tag", {}).get("member", []))

            if pa_obj["@name"] != name:
                pa.network_rename(name=pa_obj["@name"], new_name=name)

            elif pa_tags != tags or pa_desc != net.description:
                if pa_tags != tags:
                    logger.info(f"Updating tags for {name} from {pa_tags} to {tags}")
                if pa_desc != net.description:
                    logger.info(
                        f"Updating description for {name} from {pa_obj.get('description')} to {net.description}"
                    )
                pa.network_update(name=name, netmask=ip, description=net.description, tags=tags)

            else:
                logger.debug(f"Address {name} already up to date in Palo Alto")
        else:
            pa.network_create(name, ip, description=net.description, tags=tags)

    ipam_networks_by_name = set()
    for net in data.networks.values():
        name = normalize_name(net.name)
        ipam_networks_by_name.add(name)
        if net.ip4:
            create_or_update(name, net=net, v=4)

        if net.ip6:
            name = f"{name}-ip6"
            ipam_networks_by_name.add(name)
            create_or_update(name, net=net, v=6)

    deleted_msg_printed = False

    def deleted_msg():
        nonlocal deleted_msg_printed
        if not deleted_msg_printed:
            logger.info("The following networks no longer exist in IPAM:")
            deleted_msg_printed = True

    for existing_network in pa_networks:
        if existing_network["@name"] not in ipam_networks_by_name:
            deleted_msg()
            logger.info(f"Soft-Deleting {existing_network['@name']} from Palo Alto")
            name = existing_network["@name"]
            netmask = existing_network["ip-netmask"]
            description = existing_network.get("description", "")
            tags = set(existing_network.get("tag", {}).get("member", []))
            pa.network_soft_delete(name=name, netmask=netmask, description=description, tags=tags)
    if not deleted_msg_printed:
        logger.info("No ipam-sourced networks to delete from Palo Alto")

    if commit:
        pa.commit()

    logger.success("Done!")


def _debug():
    data = get_data()
    print(data)
