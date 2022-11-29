import traceback

import discord
import random
import sqlite3
import time
from bananopie import *
import json
import aiohttp


with open("config.json") as config:
    config = json.load(config)
    rpcaddress = config["rpc_address"]
    seed = config["seed"]
    discordpriv = config["discord_private_key"]
    reward = config["reward"]
    serverID = config["serverID"]


rpc = RPC(rpcaddress)


async def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


async def isactive(id):
    # bananobot does some weird rounding of IDs. IDs can be 17 or 18 characters long. Need to normalise length and then ignore rounding by ignoring last 5 characters.

    if int(id) < 18:
        remainder = 18 - len(id)
        c = 0
        while c < remainder:
            id = id + "0"
            c = c+1

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"https://bananobotapi.banano.cc/active/{serverID}") as resp:
                jsonResp = await resp.json()
                for user in jsonResp:
                    if str(id)[:-5] == str(user["id"])[:-5]:
                        return True
                return False
    except Exception as e:
        print(e)
        return False


async def getuseraddress(id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"https://bananobotapi.banano.cc/wfu/{id}") as resp:
                jsonResp = await resp.json()
                address = jsonResp[0]["address"]
                return address
    except Exception as e:
        print(e)
        return None


async def hasclaimed(id):
    location = "/claims.sqlite"
    table = "payments"
    fields = "id int, amount integer, time int, txid text"
    conn = sqlite3.connect(os.getcwd() + location)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    cur.execute(f'CREATE TABLE if not exists {table} ({fields})')
    try:
        query = """SELECT time FROM payments WHERE id =? ORDER BY time DESC LIMIT 1"""

        lastclaim = await cur.execute(query, (id,)).fetchone()
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        print("user doesn't yet exist in database")
        return False
    print((time.time() - lastclaim["time"]))
    if (time.time() - lastclaim["time"]) > 5:
        return False
    else:
        return True


async def recordclaim(id, amount, txid):
    location = "/claims.sqlite"
    table = "payments"
    fields = "id int, amount integer, time int, txid text"
    timenow = time.time()
    conn = sqlite3.connect(os.getcwd() + location)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    cur.execute(f'CREATE TABLE if not exists {table} ({fields})')
    query = """
    INSERT INTO payments(id, amount, time, txid)
    VALUES(?,?,?,?)
    """
    cur.execute(query, (id, amount, timenow, txid))
    conn.commit()
    return False


if __name__ == '__main__':
    rpc = RPC("https://kaliumapi.appditto.com/api")
    my_new_account = Wallet(rpc, seed=seed, index=0)
    my_new_account.receive_all()

    masterwallet = my_new_account.get_address()
    # get address of self
    print(f"Deposit funds to this account - {masterwallet}")

    # get balance of self
    #print(my_new_account.get_balance())

    bot = discord.Bot()


    @bot.slash_command()
    async def santa(ctx):
        user = ctx.author.name
        id = ctx.author.id
        roles = ctx.author.roles
        role = discord.utils.find(lambda r: r.name == 'citizen', ctx.guild.roles)

        rand = random.randint(0, 10)
        if role in roles:
            if await isactive(int(id)):
                if not await hasclaimed(int(id)):
                    if rand <= 7:
                        await ctx.respond(f"You were on Santa's good list! Here you go, {user}")
                        address = await getuseraddress(id)
                        print(f"sending to {address}")
                        try:
                            txid = my_new_account.send(address, 1)
                            txid = txid["hash"]
                            await recordclaim(id, reward, str(txid))
                        except Exception as e:
                            print(e)
                            traceback.print_exc()
                            await ctx.respond(f"Santa ran out of funds :(")
                    if rand > 7:
                        await ctx.respond(f"You were on Santa's naughty list! Nothing for you today, {user}")
                        await recordclaim(id, 0, "null")
                else:
                    await ctx.respond(f"You have already claimed today, {user}")
            else:
                await ctx.respond(f"You need to be active to be rewarded, {user}")


        else:
            await ctx.respond(f"You need to be a citizen to receive a gift from Santa, {user}\n Find out how to become a citizen on our wiki: <https://banano.fandom.com/citizen>")


    bot.run(discordpriv)

