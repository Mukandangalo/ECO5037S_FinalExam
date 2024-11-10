from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
import json
import base64

def init_algod():
    algod_address = "https://testnet-api.algonode.cloud"
    algod_token = ""
    return algod.AlgodClient(algod_token, algod_address)

def wait_for_confirmation(client, txid):
    try:
        last_round = client.status().get('last-round')
        txinfo = client.pending_transaction_info(txid)
        while not (txinfo.get('confirmed-round') and txinfo.get('confirmed-round') > 0):
            print("Waiting for confirmation...")
            last_round += 1
            client.status_after_block(last_round)
            txinfo = client.pending_transaction_info(txid)
        print(f"Transaction confirmed in round {txinfo.get('confirmed-round')}.")
        return txinfo
    except Exception as e:
        print(f"Error waiting for confirmation: {e}")
        return None

def create_asa(client, creator_mnemonic):
    try:
        # Get private key from mnemonic
        private_key = mnemonic.to_private_key(creator_mnemonic)
        creator_account = account.address_from_private_key(private_key)
        
        params = client.suggested_params()
        
        txn = transaction.AssetConfigTxn(
            sender=creator_account,
            sp=params,
            total=1000000,  # 1 million tokens
            decimals=6,
            default_frozen=False,
            unit_name="UCTZAR",
            asset_name="UCT South African Rand",
            manager=creator_account,
            reserve=creator_account,
            freeze=creator_account,
            clawback=creator_account,
            url="https://uct.ac.za"
        )
        
        signed_txn = txn.sign(private_key)
        txid = client.send_transaction(signed_txn)
        txinfo = wait_for_confirmation(client, txid)
        
        if txinfo:
            asset_id = txinfo["asset-index"]
            print(f"Created ASA with ID: {asset_id}")
            return asset_id
        return None
        
    except Exception as e:
        print(f"Error creating ASA: {e}")
        return None

def opt_in_asa(client, account_mnemonic, asset_id):
    try:
        private_key = mnemonic.to_private_key(account_mnemonic)
        sender = account.address_from_private_key(private_key)
        
        params = client.suggested_params()
        
        txn = transaction.AssetOptInTxn(
            sender=sender,
            sp=params,
            index=asset_id
        )
        
        signed_txn = txn.sign(private_key)
        txid = client.send_transaction(signed_txn)
        wait_for_confirmation(client, txid)
        print(f"Account {sender} opted in to asset {asset_id}")
        
    except Exception as e:
        print(f"Error opting in to ASA: {e}")

class LiquidityPool:
    def __init__(self, algo_amount, uctzar_amount, asset_id):
        self.algo_amount = algo_amount
        self.uctzar_amount = uctzar_amount
        self.asset_id = asset_id
        self.lp_tokens = {}
        self.total_fees = 0
        self.fee_rate = 0.003

    def add_liquidity(self, provider_address, algo_amount, uctzar_amount):
        try:
            if self.algo_amount == 0:
                lp_tokens = 100
            else:
                lp_tokens = (algo_amount / self.algo_amount) * 100
                
            self.algo_amount += algo_amount
            self.uctzar_amount += uctzar_amount
            
            if provider_address in self.lp_tokens:
                self.lp_tokens[provider_address] += lp_tokens
            else:
                self.lp_tokens[provider_address] = lp_tokens
                
            print(f"Added liquidity: {algo_amount} ALGO and {uctzar_amount} UCTZAR")
            print(f"LP tokens minted: {lp_tokens}")
            return lp_tokens
            
        except Exception as e:
            print(f"Error adding liquidity: {e}")
            return 0

    def remove_liquidity(self, provider_address, lp_tokens):
        try:
            if provider_address not in self.lp_tokens or self.lp_tokens[provider_address] < lp_tokens:
                raise ValueError("Insufficient LP tokens")
                
            share = lp_tokens / sum(self.lp_tokens.values())
            algo_to_return = self.algo_amount * share
            uctzar_to_return = self.uctzar_amount * share
            
            self.algo_amount -= algo_to_return
            self.uctzar_amount -= uctzar_to_return
            self.lp_tokens[provider_address] -= lp_tokens
            
            fee_share = self.total_fees * share
            algo_to_return += fee_share
            self.total_fees -= fee_share
            
            print(f"Removed liquidity: {algo_to_return} ALGO and {uctzar_to_return} UCTZAR")
            return algo_to_return, uctzar_to_return
            
        except Exception as e:
            print(f"Error removing liquidity: {e}")
            return 0, 0

    def swap_algo_to_uctzar(self, algo_amount):
        try:
            k = self.algo_amount * self.uctzar_amount
            new_algo_amount = self.algo_amount + algo_amount
            new_uctzar_amount = k / new_algo_amount
            uctzar_out = self.uctzar_amount - new_uctzar_amount
            
            fee = uctzar_out * self.fee_rate
            uctzar_out -= fee
            self.total_fees += fee
            
            self.algo_amount = new_algo_amount
            self.uctzar_amount = new_uctzar_amount + fee
            
            print(f"Swapped {algo_amount} ALGO for {uctzar_out} UCTZAR")
            return uctzar_out
            
        except Exception as e:
            print(f"Error in swap: {e}")
            return 0

    def swap_uctzar_to_algo(self, uctzar_amount):
        try:
            k = self.algo_amount * self.uctzar_amount
            new_uctzar_amount = self.uctzar_amount + uctzar_amount
            new_algo_amount = k / new_uctzar_amount
            algo_out = self.algo_amount - new_algo_amount
            
            fee = algo_out * self.fee_rate
            algo_out -= fee
            self.total_fees += fee
            
            self.uctzar_amount = new_uctzar_amount
            self.algo_amount = new_algo_amount + fee
            
            print(f"Swapped {uctzar_amount} UCTZAR for {algo_out} ALGO")
            return algo_out
            
        except Exception as e:
            print(f"Error in swap: {e}")
            return 0

def main():
    try:
        # Initialize client
        client = init_algod()
        print("Connected to Algorand node")
        
        # Use the mnemonic phrases directly instead of private keys
        accounts = [
            {
                "mnemonic": "leg problem board crew drum recall sweet forward have print casino prosper divorce can together across split absorb wide motor upon glue organ abandon always",
                "address": "F3HZPXD6TX2QXVXR6BDCCYVFCUNNW2P6T6GEK5VU5QR3Y24NY6OALCGCOQ"
            },
            {
                "mnemonic": "bus lava leaf mansion never pony urban fitness busy decide dolphin bus bulk pepper cost seat define word hockey ginger near program seed absent expand",
                "address": "2YFPIEOJEZDFJO7YIVVNJIJPC33LZZ22SV4IHZAUJACZO3SMYOZ2KUV4UI"
            }
        ]
        
        # Create UCTZAR ASA
        print("\n=== Creating UCTZAR ASA ===")
        asset_id = create_asa(client, accounts[0]["mnemonic"])
        
        if asset_id:
            # Opt-in accounts to the ASA
            print("\n=== Opting in to UCTZAR ===")
            for acc in accounts:
                opt_in_asa(client, acc["mnemonic"], asset_id)
            
            # Create liquidity pool
            pool = LiquidityPool(0, 0, asset_id)
            
            # Demonstrate liquidity provision
            print("\n=== Adding Initial Liquidity ===")
            pool.add_liquidity(accounts[0]["address"], 5, 10)  # 5 ALGO = 10 UCTZAR
            
            # Demonstrate trading
            print("\n=== Trading Examples ===")
            pool.swap_algo_to_uctzar(1)  # Swap 1 ALGO for UCTZAR
            pool.swap_uctzar_to_algo(2)  # Swap 2 UCTZAR for ALGO
            
            # Demonstrate liquidity removal
            print("\n=== Removing Liquidity ===")
            pool.remove_liquidity(accounts[0]["address"], 50)  # Remove half of LP tokens
            
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()