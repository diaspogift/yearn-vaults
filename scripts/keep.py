from brownie import accounts, network, interface, Vault, Token
from brownie.network.gas.strategies import GasNowScalingStrategy
from decimal import Decimal
from eth_utils import is_checksum_address
import requests
from time import sleep


gas_strategy = GasNowScalingStrategy()


def get_address(msg: str) -> str:
    while True:
        addr = input(msg)
        if is_checksum_address(addr):
            return addr
        print(f"I'm sorry, but '{addr}' is not a checksummed address")


def main():
    print(f"You are using the '{network.show_active()}' network")
    bot = accounts.load("bot")
    print(f"You are using: 'bot' [{bot.address}]")
    # TODO: Allow adding/removing strategies during operation
    strategies = [interface.StrategyAPI(get_address("Strategy to farm: "))]
    while input("Add another strategy? (y/[N]): ").lower() == "y":
        strategies.append(interface.StrategyAPI(get_address("Strategy to farm: ")))

    vault = Vault.at(strategies[0].vault())
    want = Token.at(vault.token())

    for strategy in strategies:
        assert (
            strategy.keeper() == bot.address
        ), "Bot is not set as keeper! [{strategy.address}]"
        assert strategy.vault() == vault.address, "Vault mismatch! [{strategy.address}]"

    while True:
        starting_balance = bot.balance()

        calls_made = 0
        for strategy in strategies:
            # Display some relevant statistics
            symbol = want.symbol()
            credit = vault.creditAvailable(strategy) / 10 ** vault.decimals()
            print(f"[{strategy.address}] Credit Available: {credit:0.3f} {symbol}")
            debt = vault.debtOutstanding(strategy) / 10 ** vault.decimals()
            print(f"[{strategy.address}] Debt Outstanding: {debt:0.3f} {symbol}")

            if strategy.tendTrigger(
                strategy.tend.estimate_gas() * gas_strategy.get_gas_price()
            ):
                try:
                    strategy.tend({"from": bot, "gas_price": gas_strategy})
                    calls_made += 1
                except:
                    print("Call failed")

            elif strategy.harvestTrigger(
                strategy.harvest.estimate_gas() * gas_strategy.get_gas_price()
            ):
                try:
                    strategy.harvest({"from": bot, "gas_price": gas_strategy})
                    calls_made += 1
                except:
                    print("Call failed")

        if calls_made > 0:
            gas_cost = (bot.balance() - starting_balance) / 10 ** 18
            print(f"Made {calls_made} calls, spent {gas_cost} on gas.")
            print(
                f"At this rate, it'll take {bot.balance() // gas_cost} harvests to run out of gas."
            )
        else:
            print("Sleeping for 60 seconds...")
            sleep(60)

        if (
            bot.balance()
            < 3  # harvests per strategy
            * len(strategies)
            * strategy.harvest.estimate_gas()
            * gas_strategy.get_gas_price()
        ):
            # Less than 3 total harvests left until empty tank!
            print(f"Need more ether please! {bot.address}")
