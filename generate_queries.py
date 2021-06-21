# NOTE: order of tokens should match the deploy script

POOLS = [
    {
        "name": "btc",
        "type": "btc",
        "table": "SwapUtils_evt_TokenSwap",
        "address": "\\x4f6A43Ad7cba042606dECaCA730d4CE0A57ac62e",
        "tokens": [
            # ticker, decimals, contract address
            ["TBTC", 18, "\\x8dAEBADE922dF735c38C80C7eBD708Af50815fAa"],
            ["WBTC", 8, "\\x2260fac5e5542a773aa44fbcfedf7c193bc2c599"],
            ["renBTC", 8, "\\xeb4c2781e4eba804ce9a9803c67d0893436bb27d"],
            ["SBTC", 18, "\\xfe18be6b3bd88a2d2a7f928d00292e7a9963cfc6"],
        ]
    },
    {
        "name": "stablecoin",
        "type": "stablecoin",
        "table": "SwapFlashLoan_evt_TokenSwap",
        "address": "\\x3911F80530595fBd01Ab1516Ab61255d75AEb066",
        "tokens": [
            # ticker, decimals, contract address
            ["DAI", 18, "\\x6b175474e89094c44da98b954eedeac495271d0f"],
            ["USDC", 6, "\\xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"],
            ["USDT", 6, "\\xdac17f958d2ee523a2206206994597c13d831ec7"],
        ]
    },
    {
        "name": "veth2",
        "type": "eth",
        "table": "SwapFlashLoan_evt_TokenSwap",
        "address": "\\xdec2157831D6ABC3Ec328291119cc91B337272b5",
        "tokens": [
            # ticker, decimals, contract address
            ["WETH", 18, "\\xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"],
            ["vETH2", 18, "\\x898BAD2774EB97cF6b94605677F43b41871410B1"],
        ]
    },
    {
        "name": "aleth",
        "type": "eth",
        "table": "SwapFlashLoan_evt_TokenSwap",
        "address": "\\xa6018520EAACC06C30fF2e1B3ee2c7c22e64196a",
        "tokens": [
            # ticker, decimals, contract address
            ["WETH", 18, "\\xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"],
            ["alETH", 18, "\\x0100546F2cD4C9D97f798fFC9755E47865FF7Ee6"],
            ["sETH", 18, "\\x5e74c9036fb86bd7ecdcb084a0673efc32ea31cb"],
        ]
    },
]


def main():
    # need to update for new prices when adding non-eth/btc/stablecoin tokens
    # generate_total_usd_tvl_query()

    # generate_unique_deposit_addresses_query()

    # generate_cumulative_usd_volume()

    # need to create a new query when a new pool is added
    # select "area chart" viz and "enable stacking"
    # then add each new token as a Y column in "result data"
    generate_pool_liquidity_by_asset_queries()

TOKEN_DEPOSIT_WITHDRAW_TEMPLATE = """%s as
(
SELECT
date_trunc('hour', evt_block_time) as Date,
sum(value / 1e%s) as %s_val
FROM erc20."ERC20_evt_Transfer"
WHERE "to" = '%s'
AND contract_address = '%s'
GROUP BY 1
UNION ALL
SELECT
date_trunc('hour', evt_block_time) as Date,
-sum(value / 1e%s) as %s_val
FROM erc20."ERC20_evt_Transfer"
WHERE "from" = '%s'
AND contract_address = '%s'
GROUP BY 1
),
"""
TOTALS_TEMPLATE = """
totals as
(
SELECT
Date,
%s
FROM
(
%s
) t
GROUP BY 1
ORDER BY 1 DESC
LIMIT 1
)
"""
PRICE_TEMPLATE = """
SELECT
%s as total_tvl_usd
FROM totals
LEFT JOIN prices."layer1_usd" p ON p.minute = Date
LEFT JOIN prices."layer1_usd" p2 ON p2.minute = Date
WHERE p.symbol = 'BTC' AND p2.symbol = 'ETH'
GROUP BY p.price, p2.price
"""
def generate_total_usd_tvl_query():
    query = "WITH "
    sum_queries = []
    token_vals = []
    totals = []
    prices = []
    for pool in POOLS:
        pool_token_vals = []
        for token in pool["tokens"]:
            ticker, decimals, address = token
            identifier = "%s_%s" % (pool["name"], ticker)
            query += TOKEN_DEPOSIT_WITHDRAW_TEMPLATE % (
                identifier,
                decimals, identifier,
                pool["address"],
                address,
                decimals, identifier,
                pool["address"],
                address
            )
            sum_queries.append("sum(sum(%s_val)) over (order by Date) as %s_val" % (identifier, identifier))
            token_vals.append("%s_val" % identifier)
            pool_token_vals.append("%s_val" % identifier)
        price_arg = "1"
        if pool["type"] is "btc":
            price_arg = "p.price"
        elif pool["type"] is "eth":
            price_arg = "p2.price"
        prices.append("sum(%s) * %s" % (" + ".join(pool_token_vals), price_arg))

    padded_query = "\tSELECT Date, "
    for t in token_vals:
        padded_query += "0 as %s, " % t
    # trim extra comma
    padded_query = padded_query[:-2]

    for t in token_vals:
        fixed = padded_query.replace("0 as %s" % t, t)
        totals.append("%s FROM %s" % (fixed, t.replace("_val", "")))

    query += TOTALS_TEMPLATE % (
        ',\n'.join(sum_queries),
        "\tUNION ALL\n".join(totals)
    )
    query += PRICE_TEMPLATE % " + ".join(prices)

    print query

DEPOSIT_TEMPLATE="""
SELECT
"from" as addr
FROM erc20."ERC20_evt_Transfer"
WHERE "to" = '%s'
GROUP BY 1
UNION ALL
SELECT
"to" as addr
FROM erc20."ERC20_evt_Transfer"
WHERE "from" = '%s'
GROUP BY 1
"""
DISTINCT_TEMPLATE=""")

SELECT
count(DISTINCT addr) as "Distinct Addresses"
FROM saddle
"""
def generate_unique_deposit_addresses_query():
    query = "WITH saddle as ("
    interactions = []
    for pool in POOLS:
        interactions.append(DEPOSIT_TEMPLATE % (pool["address"], pool["address"]))
    query += "UNION ALL".join(interactions)
    query += DISTINCT_TEMPLATE

    print query

VOLUME_TEMPLATE = """
SELECT
date_trunc('day', evt_block_time) as Date,
sum("tokensBought" / 1e%s) * p.price as usd_volume
FROM saddle."%s" s
LEFT JOIN %s p ON p.minute = date_trunc('day', evt_block_time)
WHERE "boughtId" = %s
AND s.contract_address = '%s'
AND p.symbol = '%s'
GROUP BY 1, p.price
"""
VOLUME_STABLECOIN_TEMPLATE = """
SELECT
date_trunc('day', evt_block_time) as Date,
sum("tokensBought" / 1e%s) as usd_volume
FROM saddle."%s"
WHERE "boughtId" = %s
AND contract_address = '%s'
GROUP BY 1
"""
VOLUME_SELECT_TEMPLATE = """
)

SELECT
sum(usd_volume) as "USD Volume"
FROM volume
"""
def generate_cumulative_usd_volume():
    query = "WITH volume as ("
    volumes = []
    for pool in POOLS:
        price_table = 'prices."layer1_usd"'
        symbol = "BTC"
        if pool["type"] is "eth":
            symbol = "ETH"
        for idx, token in enumerate(pool["tokens"]):
            ticker, decimals, address = token
            if pool["type"] is "stablecoin":
                volumes.append(VOLUME_STABLECOIN_TEMPLATE % (
                    decimals,
                    pool["table"],
                    idx,
                    pool["address"],
                ))
            else:
                volumes.append(VOLUME_TEMPLATE % (
                    decimals,
                    pool["table"],
                    price_table,
                    idx,
                    pool["address"],
                    symbol
                ))
    query += "UNION ALL".join(volumes)
    query += VOLUME_SELECT_TEMPLATE

    print query

def generate_pool_liquidity_by_asset_queries():
    for pool in POOLS:
        query = "WITH "
        sum_queries = []
        pool_token_vals = []
        totals = []
        for token in pool["tokens"]:
            ticker, decimals, address = token
            # identifier = "%s_%s" % (pool["name"], ticker)
            identifier = ticker
            query += TOKEN_DEPOSIT_WITHDRAW_TEMPLATE % (
                identifier,
                decimals, identifier,
                pool["address"],
                address,
                decimals, identifier,
                pool["address"],
                address
            )
            sum_queries.append('sum(sum(%s_val)) over (order by Date) as "%s"' % (identifier, identifier))
            pool_token_vals.append("%s_val" % identifier)

        padded_query = "\tSELECT Date, "
        for t in pool_token_vals:
            padded_query += "0 as %s, " % t
        # trim extra comma
        padded_query = padded_query[:-2]

        for t in pool_token_vals:
            fixed = padded_query.replace("0 as %s" % t, t)
            totals.append("%s FROM %s" % (fixed, t.replace("_val", "")))

        query += TOTALS_TEMPLATE % (
            ',\n'.join(sum_queries),
            "\tUNION ALL\n".join(totals)
        )
        query = query.replace("LIMIT 1", "")
        query += "\nSELECT * FROM totals"

        print query

        print "\n============================================================\n"

if __name__ == "__main__":
    main()
