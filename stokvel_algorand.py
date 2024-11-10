from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from algosdk.transaction import PaymentTxn, Multisig, MultisigTransaction
import random
import time

# Algorand TestNet parameters
ALGOD_URL = "https://testnet-api.algonode.cloud"
ALGOD_TOKEN = ""  # Public endpoint, no token required
algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_URL)

# Stokvel members - Replace with your funded TestNet accounts
members = [
    {"address": "F3HZPXD6TX2QXVXR6BDCCYVFCUNNW2P6T6GEK5VU5QR3Y24NY6OALCGCOQ", 
     "private_key": "+ttqMTTDoc1221tNs+pGyAqgg3RcApE2QPUHefePjRMuz5fcfp31C9bx8EYhYqUVGttp/p+MRXa07CO8a43HnA=="},
    {"address": "2YFPIEOJEZDFJO7YIVVNJIJPC33LZZ22SV4IHZAUJACZO3SMYOZ2KUV4UI", 
     "private_key": "93Bf/XSIyp/q/Vf5MI6B7gGPixZGwsxZ/9ggxsmvXrjWCvQRySZGVLv4RWrUoS8W9rznWpV4g+QUSAWXbkzDsw=="},
    {"address": "YFSJ23C2EYHMGEC5S3MGFF6JXITXIYMO6JVMHHTLRCDKWH7D726Z46RQLU", 
     "private_key": "Bg/eqNlTKMJXpLhAdtcI7sa1Mx6gHjTKMarFp4Gv+A3BZJ1sWiYOwxBdlthil8m6J3RhjvJqw55riIarH+P+vQ=="},
    {"address": "ZBAQBJC66FLNKDLTUEKLBLBXBKFBBFN6LBOQS2KYPM5Q2V2TWXIOR6WS3Y", 
     "private_key": "XrrryM6VPe0aoz/dUrtVaERJkwkac0fAa2F3a1w89BHIQQCkXvFW1Q1zoRSwrDcKihCVvlhdCWlYezsNV1O10A=="},
    {"address": "Z5IE4PCZOL3EU7DNQR5ZLYTRODASZ6ASVOOXYCQN7OU4LAN2VJ7DPY4N3U", 
     "private_key": "BYwxK+n6/Zz/nS8ZxFdoAGWIYxjjKSMVQ0WuV4V0Q2zPUE48WXL2SnxthHuV4nFwwSz4EqudfAoN+6nFgbqqfg=="}
]

def check_balance(address):
    """Check if account has sufficient balance"""
    try:
        account_info = algod_client.account_info(address)
        return account_info.get('amount', 0)
    except Exception as e:
        print(f"Error checking balance: {str(e)}")
        return 0

def wait_for_confirmation(txid):
    """Wait until the transaction is confirmed or rejected"""
    try:
        last_round = algod_client.status().get('last-round')
        while True:
            txinfo = algod_client.pending_transaction_info(txid)
            if txinfo.get('confirmed-round', 0) > 0:
                print(f"Transaction {txid} confirmed in round {txinfo.get('confirmed-round')}.")
                return txinfo
            elif txinfo.get('pool-error'):
                print(f"Transaction {txid} failed: {txinfo['pool-error']}")
                return None
            last_round += 1
            algod_client.status_after_block(last_round)
    except Exception as e:
        print(f"Error waiting for confirmation: {str(e)}")
        return None

# Create multisig account requiring 4-of-5 signatures
msig = Multisig(version=1, threshold=4, addresses=[m["address"] for m in members])
print(f"Stokvel Multisig Address: {msig.address()}")

def fund_multisig_account():
    """Process monthly deposits from all members"""
    print("\nProcessing monthly deposits...")
    successful_deposits = 0

    for member in members:
        try:
            # Check member's balance
            balance = check_balance(member["address"])
            if balance < 5_000_000:  # 5 Algos
                print(f"Insufficient balance for {member['address']}: {balance} microAlgos")
                continue

            # Get suggested parameters and modify for optimal fee handling
            params = algod_client.suggested_params()
            params.flat_fee = True
            params.fee = 1000  # 0.001 Algos

            # Create and sign deposit transaction
            txn = PaymentTxn(
                sender=member["address"],
                receiver=msig.address(),
                amt=5_000_000,  # 5 Algos
                sp=params
            )
            signed_txn = txn.sign(member["private_key"])
            
            # Submit transaction
            txid = algod_client.send_transaction(signed_txn)
            
            # Wait for confirmation
            if wait_for_confirmation(txid):
                successful_deposits += 1
                print(f"Deposit confirmed from {member['address']}")
            
            time.sleep(2)  # Wait between transactions
            
        except Exception as e:
            print(f"Error processing deposit from {member['address']}: {str(e)}")

    return successful_deposits == len(members)

def select_and_pay_recipient(paid_members):
    """Process monthly payout to randomly selected member"""
    # Check multisig account balance
    msig_balance = check_balance(msig.address())
    if msig_balance < 15_000_000:  # 15 Algos
        print(f"Insufficient balance in multisig account: {msig_balance} microAlgos")
        return None

    # Select eligible recipient
    eligible_members = [m for m in members if m["address"] not in paid_members]
    if not eligible_members:
        print("No eligible recipients remaining")
        return None

    recipient = random.choice(eligible_members)
    print(f"\nSelected recipient: {recipient['address']}")

    try:
        # Get suggested parameters
        params = algod_client.suggested_params()
        params.flat_fee = True
        params.fee = 1000  # 0.001 Algos

        # Create payout transaction
        payout_txn = PaymentTxn(
            sender=msig.address(),
            receiver=recipient["address"],
            amt=15_000_000,  # 15 Algos
            sp=params
        )

        # Create multisig transaction and collect signatures
        mtx = MultisigTransaction(payout_txn, msig)
        for i in range(4):  # Get 4 signatures (80% requirement)
            mtx.sign(members[i]["private_key"])

        # Submit transaction
        txid = algod_client.send_transaction(mtx)
        
        # Wait for confirmation
        if wait_for_confirmation(txid):
            print(f"Payout confirmed to {recipient['address']}")
            return recipient["address"]
        
        return None

    except Exception as e:
        print(f"Error processing payout: {str(e)}")
        return None

def run_stokvel_cycle():
    """Run a complete 5-month stokvel cycle"""
    print("\nStarting stokvel cycle...")
    paid_members = set()

    for month in range(1, 6):
        print(f"\n=== Month {month} ===")

        # Day t: Process deposits
        if not fund_multisig_account():
            print(f"Failed to collect all deposits for month {month}")
            return False

        # Day t+1: Process payout
        time.sleep(2)  # Simulate next day
        recipient = select_and_pay_recipient(paid_members)
        if recipient:
            paid_members.add(recipient)
        else:
            print(f"Failed to process payout for month {month}")
            return False

        time.sleep(3)  # Wait between months

    print("\nStokvel cycle completed successfully!")
    return True

# Entry point
if __name__ == "__main__":
    print("Starting Stokvel Application")
    print("============================")
    print("Configuration:")
    print("- Number of members: 5")
    print("- Monthly deposit: 5 Algos")
    print("- Monthly payout: 15 Algos")
    print("- Required signatures: 4 of 5")
    print("============================")
    
    run_stokvel_cycle()
