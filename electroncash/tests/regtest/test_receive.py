from bitcoinrpc.authproxy import AuthServiceProxy
import pytest
import time
import os

from ... import SimpleConfig, Network
from ...wallet import create_new_wallet
from ... import networks

def bitcoind_rpc_connection():
    bitcoind = AuthServiceProxy("http://user:pass@0.0.0.0:18333")

    block_count = bitcoind.getblockcount()
    if block_count < 101:
        bitcoind.generate(101)

    return bitcoind

def clean_data_dir():
    import shutil
    if os.path.isdir("/tmp/ec_regtest"):
        shutil.rmtree("/tmp/ec_regtest")
    os.mkdir("/tmp/ec_regtest")

def get_config():
    config_options = {}
    clean_data_dir()
    config_options['wallet_path'] = "/tmp/ec_regtest/ec_wallet"
    config_options['electron_cash_path'] = "/tmp/ec_regtest/ec_data"
    config_options['regtest'] = True
    config_options['cwd'] = os.getcwd()
    c = SimpleConfig(config_options)
    c.user_config['server'] = 'localhost:50002:s'
    return c

def get_wallet(config, network):
    new_wallet = create_new_wallet(path=config.cmdline_options['wallet_path'],config=config)
    wallet = new_wallet['wallet']
    wallet.start_threads(network)
    wallet.synchronize()
    return wallet

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return os.path.join(str(pytestconfig.rootdir), "electroncash/tests/regtest/docker-compose.yml")

@pytest.fixture(scope="session")
def fulcrum_service(docker_services):
    time.sleep(10)

current_height = 0
def test_blockcount(fulcrum_service):
    bitcoind = bitcoind_rpc_connection()
    time.sleep(5)
    networks.set_regtest()
    config = get_config()

    network = Network(config)
    network.start()

    while network.is_connecting():
        time.sleep(0.1)
    if not network.is_connected():
        assert False

    start_height = bitcoind.getblockcount()
    def callback(event, *args):
        global current_height
        _, current_height = network.get_status_value('blockchain_updated')
    network.register_callback(callback, ['blockchain_updated'])

    bitcoind.generate(12)
    now = time.time()
    global current_height
    while network.is_connected() and time.time() - now < 5 and current_height - start_height < 12:
        time.sleep(1)

    assert current_height - start_height == 12
    network.stop()

def test_receive_coin(fulcrum_service):
    bitcoind = bitcoind_rpc_connection()
    time.sleep(5)

    networks.set_regtest()
    config = get_config()

    network = Network(config)
    network.start()

    while network.is_connecting():
        time.sleep(0.1)
    if not network.is_connected():
        assert False
    block_count = bitcoind.getblockcount()
    wallet = get_wallet(config, network)
    addr = wallet.get_addresses()[0].to_ui_string()
    orig_balance_c, _, orig_balance_x = wallet.get_balance()
    bitcoind.generatetoaddress(1, addr)
    time.sleep(3)
    _, _, new_balance = wallet.get_balance()
    assert new_balance - orig_balance_x == 5000000000

    bitcoind.generate(100)
    time.sleep(3)
    new_balance, _, _ = wallet.get_balance()
    assert new_balance - orig_balance_c == 5000000000
    network.stop()
