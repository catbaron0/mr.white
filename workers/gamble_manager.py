# 双方以投骰子积分来进行游戏，最先把积分累计到4000者胜出
# 双方各持六个D6骰子
# 其中，2、3、4、6必须为三个为同一数才能计分，比如，三个2，记200分，三个3记三百分，单个和两个不计分。四个同样的数字，则翻倍，比如四个2则是400分，五个同样的数字则再翻倍，五个2为800分，六个同样的数字则再翻倍，6个2为1600分。
# 而1和5则可以单独一个就能计分，1为100，5为50。
# 三个1为1000分，四个1为2000分，五个1为4000分，同理三个5为500分··········
# 12345和23456为500分，123456为1500分
# 也就意味着，如果你开局刷到了5个1及以上点数，将直接结束比赛。
# 游戏开始后，开始投骰子，骰子的结果里，有可以计分的点数骰子，你将可以把其拿出来，并写上临时的计分里，然后可以选择继续投剩下的骰子，直到你选择计分并结束回合，或者投出没有任何计分的点数。
# 当选择计分结束回合时，临时的计分则会成为你的真实积分，而当没有投出任何可以计分点数时，所有临时计分将清零，并跳过你的回合。

import random
import logging

from discord import User, Member, Reaction, Message
from discord.ext import commands


LOG = logging.getLogger(__name__)


def score_1_or_5(roll: list[int], num: int) -> list[dict]:
    base_scores = 100 if num == 1 else 50
    results = []
    count = roll.count(num)

    if count >= 1:
        score = base_scores
        results.append({"score": score, "remove": [num]})
    if count >= 3:
        score = base_scores * 10
        results.append({"score": score, "remove": [num] * 3})
    if count >= 4:
        score = base_scores * 20
        results.append({"score": score, "remove": [num] * 4})
    if count >= 5:
        score = base_scores * 40
        results.append({"score": score, "remove": [num] * 5})
    if count >= 6:
        score = base_scores * 80
        results.append({"score": score, "remove": [num] * 6})
    return results


def score_2_to_6(roll: list[int], num: int) -> list[dict]:
    results = []
    count = roll.count(num)

    if count >= 3:
        score = num * 100
        results.append({"score": score, "remove": [num] * 3})
    if count >= 4:
        score = num * 200
        results.append({"score": score, "remove": [num] * 4})
    if count == 5:
        score = num * 400
        results.append({"score": score, "remove": [num] * 5})
    if count == 6:
        score = num * 400
        results.append({"score": score, "remove": [num] * 6})
    return results


def score_straights(roll: list[int]) -> list[dict]:
    results = []
    unique_roll = set(roll)

    # 检查顺子12345
    if all(num in unique_roll for num in range(1, 6)):
        results.append({"score": 500, "remove": [1, 2, 3, 4, 5]})

    # 检查顺子23456
    if all(num in unique_roll for num in range(2, 7)):
        results.append({"score": 500, "remove": [2, 3, 4, 5, 6]})

    # 检查大顺子123456
    if all(num in unique_roll for num in range(1, 7)):
        results.append({"score": 1500, "remove": [1, 2, 3, 4, 5, 6]})

    return results


def compute_score(roll: list[int]) -> list[dict]:
    results = []

    results += score_1_or_5(roll, 1)
    results += score_1_or_5(roll, 5)
    for num in [2, 3, 4, 6]:
        results += score_2_to_6(roll, num)
    results += score_straights(roll)
    for i in range(len(results)):
        results[i]["is_selected"] = False
    return results


def idx_to_emoji(idx: int) -> str:
    """将 0-25 转换为 🇦 - 🇿"""
    if not 0 <= idx < 10:
        raise ValueError("Index out of range for emoji conversion")
    # 🇦 的 Unicode 是 U+1F1E6

    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    return number_emojis[idx]


def emoji_to_idx(emoji: str) -> int:
    """将 🇦 - 🇿 转换为 0-25"""
    number_emojis = {
        "1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3, "5️⃣": 4,
        "6️⃣": 5, "7️⃣": 6, "8️⃣": 7, "9️⃣": 8, "🔟": 9,
    }
    if emoji not in number_emojis:
        raise ValueError("Invalid emoji for index conversion")
    return number_emojis[emoji]


class Player:
    def __init__(self, member: Member | User, ctx, dice_count: int = 6):
        self.member = member
        self.total_score = 0
        self.init_dice_count = dice_count
        self.win = False
        self.is_playing = False
        self.ctx = ctx
        self.new_turn()

    def new_turn(self):
        self.turn = Turn(self.init_dice_count, self.ctx, self.member, total_score=self.total_score)

    def end_turn(self):
        if self.turn:
            self.total_score += self.turn.turn_score
        self.win = self.total_score >= 4000
        self.is_playing = False


class Turn:
    def __init__(self,  dice_count: int, ctx, member: Member | User, total_score: int = 0):
        self.round_score = 0
        self.turn_score = 0
        self.member = member
        self.ctx = ctx
        self.roll_results: list[list[int]] = []
        self.roll = []
        self.score_candidates = []
        self.dice_count = dice_count
        self.is_failed = False
        self.roll_msg = None
        self.total_score = total_score
        self.current_dice_count = [0]
        self.emojis = set()

    def update_dice_count(self):
        self.dice_count = sum(self.current_dice_count)

    def update_turn_score(self):
        self.turn_score += self.round_score
        self.round_score = 0

    def is_any_selected(self) -> bool:
        return any(candidate["is_selected"] for candidate in self.score_candidates)

    async def roll_dice(self):
        roll = [random.randint(1, 6) for _ in range(self.dice_count)]
        self.roll = roll
        self.roll_results.append([roll.count(i) for i in range(0, 7)])
        self.score_candidates = compute_score(roll)
        await self.display_removal_choices()
        self.is_failed = len(self.score_candidates) == 0

    def generate_choice_message(self, alert: str) -> tuple[str, list[str]]:
        resp = ""
        if self.dice_count == 6:
            resp += "# =================================\n"
        else:
            resp += "# --------------------------\n"
        resp += f"【{self.member.mention}】投出了: `{', '.join(str(d) for d in self.roll)}`\n\n"
        emojis = [idx_to_emoji(i) for i in range(len(self.score_candidates))]
        if emojis:
            resp += "可选得分方案：\n"
        for i, candidate in enumerate(self.score_candidates):
            score = candidate["score"]
            remove = candidate["remove"]
            emoji = emojis[i]
            choice = f"{emoji} 移除骰子 {remove}, 得分 {score}"
            if candidate["is_selected"]:
                choice = f"~~{choice}~~"
            resp += f"{choice}\n"
        resp += f"\n当前总得分: {self.total_score} 分\n"
        resp += f"本轮临时积分: {self.turn_score} 分\n"
        resp += f"*当前临时积分: {self.round_score} 。*\n"
        if alert:
            resp += f"**{alert}**\n"
        return resp, emojis

    async def display_removal_choices(self):
        if not self.score_candidates:
            self.turn_score = 0
            resp, emojis = self.generate_choice_message("")
            self.is_finished = True
            resp += "\n⚠️次投骰无可计分点数，回合结束，本轮临时积分清零。"
            msg = await self.ctx.channel.send(resp)
        else:
            resp, emojis = self.generate_choice_message("")
            msg = await self.ctx.channel.send(resp)
            emojis.append("➡️")
            emojis.append("✅")
            emojis.append("👀")
            emojis.append("❌")
            for emoji in emojis:
                await msg.add_reaction(emoji)
            self.roll_msg = await msg.channel.fetch_message(msg.id)

    async def update_choice_message(self, alert: str = ""):
        resp, emojis = self.generate_choice_message(alert)
        if self.roll_msg:
            await self.roll_msg.edit(content=resp)
        else:
            await self.ctx.channel.send(resp)

    async def select_option(self):
        self.round_score = 0
        self.current_dice_count = [self.roll.count(i) for i in range(7)]
        LOG.info("current_dice_count:", self.current_dice_count)

        emojis = self.emojis
        for i in range(len(self.score_candidates)):
            self.score_candidates[i]["is_selected"] = False
        for emoji in emojis:
            try:
                idx = emoji_to_idx(emoji)
            except ValueError:
                continue
            if idx < 0 or idx >= len(self.score_candidates):
                continue
            self.score_candidates[idx]["is_selected"] = True
            removal = self.score_candidates[idx]["remove"]
            self.round_score += self.score_candidates[idx]["score"]
            for i in range(7):
                self.current_dice_count[i] -= removal.count(i)
        alert = ""
        if any([i < 0 for i in self.current_dice_count]):
            alert = "```\n"
            alert += "你已经选择了超过可用骰子的得分方案，请调整选择。"
            alert += "```"
        await self.update_choice_message(alert)


class GambleGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.players: list[Player] = []
        self.current_player_index: int = -1
        self.start_message: Message | None = None
        self.is_finished: bool = False

        start_content = ""
        start_content += "## 🎲 骰子游戏开始\n"
        start_content += "- 🙋‍♂️ 加入游戏\n"
        start_content += "- 🏁 开始游戏\n"
        start_content += "- 🔟 选择得分方案\n"
        start_content += "- ➡️ 确定方案并进入下一回合\n"
        start_content += "- ✅ 计入分数并切换至下一名玩家\n"
        start_content += "- 👀 列出当前分数\n"
        start_content += "- ❌ 移除当前玩家(剩余玩家可继续)。\n"
        start_content += "- 详细规则：https://discord.com/channels/808893235103531039/1429127004959146045/1429127004959146045\n"
        self.start_content = start_content

    def current_player(self) -> Player | None:
        if self.current_player_index == -1:
            return None
        return self.players[self.current_player_index]

    async def prepare_game(self):
        """
        start a new gamble game.
        Send a message to the channel to indicate the game has started.
        Players can join the game by reacting to the message.
        """
        self.players = []
        self.current_player_index = -1
        self.start_message = await self.ctx.message.reply(self.start_content)
        join_emoji = "🙋‍♂️"
        start_emoji = "🏁"
        if self.start_message:
            await self.start_message.add_reaction(join_emoji)
            await self.start_message.add_reaction(start_emoji)
            self.start_message = await self.start_message.channel.fetch_message(self.start_message.id)

    def join(self, member: Member | User):
        if member not in [p.member for p in self.players]:
            self.players.append(Player(member, self.ctx))

    def next_player(self, player: Player | None = None):
        if player and player != self.current_player():
            return
        if self.current_player_index == -1:
            self.current_player_index = 0
        else:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            self.players[self.current_player_index].new_turn()

    async def next_turn(self):
        # first turn
        if self.current_player_index == -1:
            self.current_player_index = 0

        # the current player plays his turn
        current_player = self.players[self.current_player_index]

        await current_player.turn.roll_dice()
        if current_player.turn.is_failed:
            self.next_player(current_player)
            await self.next_turn()

    async def on_reaction_add(self, reaction: Reaction, user: User | Member):
        if user.bot or not reaction.message.guild:
            return

        # join game
        if self.start_message and reaction.message.id == self.start_message.id and reaction.emoji == "🙋‍♂️":
            resp = self.start_content
            resp += "\n--------------------------"
            for reaction in self.start_message.reactions:
                if reaction.emoji != "🙋‍♂️":
                    continue
                if user not in [p.member for p in self.players]:
                    self.join(user)
                break
            for player in self.players:
                resp += f"\n*{player.member.mention}入了游戏！*"
            self.start_message = await self.start_message.edit(content=resp)
            return

        # start game
        if self.start_message and reaction.message.id == self.start_message.id and reaction.emoji == "🏁":
            if len(self.players) < 2:
                resp = self.start_content
                for player in self.players:
                    resp += f"\n{player.member.display_name} 加入了游戏！"
                resp += "\n❌ 游戏至少需要两名玩家才能开始。"
                self.start_message = await self.start_message.edit(content=resp)
                return
            await self.ctx.channel.send("游戏开始！")
            await self.next_turn()
            return

        current_player = self.current_player()
        roll_msg = current_player.turn.roll_msg if current_player else None
        # show scores or quit game
        if roll_msg and reaction.message.id == roll_msg.id:
            if reaction.emoji == "❌":
                # remove user
                for p in self.players:
                    if p.member == user:
                        self.players.remove(p)
                        await self.ctx.channel.send(f"{user.display_name} 已退出游戏。")
                        if len(self.players) < 2:
                            await self.ctx.channel.send("❌ 玩家不足两人，游戏结束。")
                            self.is_finished = True
                        else:
                            if p == current_player:
                                self.next_player()
                                await self.next_turn()
                        break
                return
            elif reaction.emoji == "👀":
                # show scores
                await self.show_scores()
                return

        # select options during turn
        if current_player and user == current_player.member and roll_msg and reaction.message.id == roll_msg.id:
            if reaction.emoji == "✅" or reaction.emoji == "➡️":
                # end turn
                if not current_player.turn.is_any_selected():
                    alert = "```\n"
                    alert += "你必须选择至少一个得分方案才能结束回合。"
                    alert += "```"
                    await self.players[self.current_player_index].turn.update_choice_message(alert)
                    return
                if any([i < 0 for i in current_player.turn.current_dice_count]):
                    return
                self.players[self.current_player_index].turn.update_turn_score()
                self.players[self.current_player_index].turn.update_dice_count()
                
                if reaction.emoji == "✅" or self.players[self.current_player_index].turn.dice_count <= 0:
                    self.players[self.current_player_index].end_turn()
                    if self.players[self.current_player_index].win:
                        await self.ctx.channel.send(f"🎉 {user.display_name} 胜出，游戏结束！")
                        self.is_finished = True
                        return
                    total_score = self.players[self.current_player_index].total_score
                    turn_score = self.players[self.current_player_index].turn.turn_score
                    await self.ctx.channel.send(
                        f"{user.display_name} 本回合结束，累计积分 {total_score}(+{turn_score}) 分。"
                    )
                    self.next_player(current_player)
                await self.next_turn()
                return

            else:
                self.players[self.current_player_index].turn.emojis.add(reaction.emoji)
                await self.players[self.current_player_index].turn.select_option()

    async def on_reaction_remove(self, reaction: Reaction, user: User | Member):
        if user.bot or not reaction.message.guild:
            return

        # quit game
        if self.start_message and reaction.message.id == self.start_message.id and reaction.emoji == "🙋‍♂️":
            resp = self.start_content
            for reaction in self.start_message.reactions:
                if reaction.emoji != "🙋‍♂️":
                    continue
                for p in self.players:
                    if p.member == user:
                        self.players.remove(p)
                for player in self.players:
                    resp += f"\n{player.member.display_name} 加入了游戏！"
                break
            self.start_message = await self.start_message.edit(content=resp)
            return

        # unselect options during turn
        player = self.current_player()
        roll_msg = player.turn.roll_msg if player else None
        if player and user == player.member and roll_msg and reaction.message.id == roll_msg.id:
            self.players[self.current_player_index].turn.emojis.discard(reaction.emoji)
            await self.players[self.current_player_index].turn.select_option()

    async def show_scores(self):
        resp = ""
        for player in self.players:
            resp += f"- {player.member.display_name}: {player.total_score}\n"
        await self.ctx.channel.send(resp)


class GambleDelegater(commands.Cog):
    def __init__(self):
        self.games = {}

    async def new_game(self, ctx):
        # clean empty games
        self.games = {c: g for c, g in self.games.items() if g.players}
        game = GambleGame(ctx)
        self.games[ctx.channel.id] = game
        await game.prepare_game()

    async def show_scores(self, channel_id):
        if channel_id in self.games:
            await self.games[channel_id].show_scores()

    async def run(self, ctx, *args):
        LOG.info(f"GambleDelegater run with args: {args}")
        if not args or not args[0] or args[0] == "new":
            await self.new_game(ctx)
        if args[0] == "scores":
            await self.show_scores(ctx.channel.id)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild:
            return
        game = self.games.get(reaction.message.channel.id)
        if game:
            await game.on_reaction_add(reaction, user)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: Reaction, user: Member | User):
        if user.bot or not reaction.message.guild:
            return
        game = self.games.get(reaction.message.channel.id)
        if game:
            await game.on_reaction_remove(reaction, user)
