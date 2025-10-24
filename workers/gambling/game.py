import random

import discord
from discord import User, Member, Interaction, Message
from workers.gambling.dispatcher import Dispatcher
from workers.gambling.signals import RollSignal

import workers.gambling.utils as utils


class Player:
    def __init__(self, member: Member | User, dice_count: int = 6):
        self.member = member
        self.score = 0
        self.init_dice_count = dice_count
        self.dice_count = dice_count
        self.win = False

    def update_dice_count(self, dice_count: int):
        if dice_count == 0:
            dice_count = self.init_dice_count
        self.dice_count = dice_count

    def reset_dice(self):
        self.dice_count = self.init_dice_count


class Game:
    def __init__(self):
        self.players: list[Player] = []
        self.current_player_index: int = -1
        self.winner: Player | None = None

    @property
    def current_player(self) -> Player | None:
        if self.current_player_index == -1:
            return None
        return self.players[self.current_player_index]

    @property
    def player_count(self) -> int:
        return len(self.players)

    def is_player_in(self, member: Member | User) -> bool:
        return member in [p.member for p in self.players]

    def add_player(self, member: Member | User):
        self.players.append(Player(member))

    def remove_player(self, member: Member | User):
        for p in self.players:
            if p.member == member:
                self.players.remove(p)
                break

    def next_player(self):
        if self.current_player_index == -1:
            self.current_player_index = 0
        else:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
        assert self.current_player is not None
        self.current_player.reset_dice()

    async def end_game(self, click_interaction: Interaction):
        assert self.winner is not None
        resp = f"🎉 恭喜 {self.winner.member.mention} 获得胜利！最终积分: {self.winner.score} 分 🎉"
        resp += "\n\n最终积分榜:\n"
        players = sorted(self.players, key=lambda p: p.score, reverse=True)
        for player in players:
            resp += f"1. {player.member.display_name}: {player.score} 分\n"
        await click_interaction.followup.send(resp)

    def generate_message_content(self) -> str:
        content = ""
        content += "## 🎲 骰子游戏\n"
        content += "详细规则：https://discord.com/channels/808893235103531039/1429127004959146045/1429127004959146045\n"
        if self.player_count > 0:
            content += "\n```\n"
            for player in self.players:
                content += f"@{player.member.display_name} 已加入游戏！\n"
            content += '```'
        return content


class Turn:
    def __init__(self,  game: Game, dispatcher: Dispatcher):
        self.dispatcher = dispatcher
        self.game = game
        self.roll_score = 0
        self.turn_score = 0

        self.roll = []
        self.dice_point_counts = [0] * 7
        self.score_candidates = []

        self.is_failed = False
        self.roll_dice()

    def is_any_selected(self) -> bool:
        return any(candidate["is_selected"] for candidate in self.score_candidates)

    def is_ok_to_submit(self) -> bool:
        return self.is_any_selected() and all(i >= 0 for i in self.dice_point_counts)

    def finish(self):
        self.turn_score += self.roll_score

        assert self.game.current_player is not None
        self.game.current_player.update_dice_count(sum(self.dice_point_counts))

    def submit_score(self):
        assert self.game.current_player is not None
        self.game.current_player.score += self.turn_score
        if self.game.current_player.score >= 4000:
            self.game.current_player.win = True
            self.game.winner = self.game.current_player

    def roll_dice(self):
        assert self.game.current_player is not None
        roll = [random.randint(1, utils.DICE_FACE_COUNT) for _ in range(self.game.current_player.dice_count)]
        self.roll = roll
        self.dice_point_counts = [roll.count(i) for i in range(0, utils.DICE_FACE_COUNT + 1)]
        self.score_candidates = utils.compute_score(roll)
        self.is_failed = len(self.score_candidates) == 0

    def update_selection(self, idx: int):
        if idx < 0 or idx >= len(self.score_candidates):
            return

        removed_dices = self.score_candidates[idx]["remove"]
        self.score_candidates[idx]["is_selected"] = not self.score_candidates[idx]["is_selected"]

        if self.score_candidates[idx]["is_selected"]:
            self.roll_score += self.score_candidates[idx]["score"]
            for i in range(7):
                self.dice_point_counts[i] -= removed_dices.count(i)
        else:
            self.roll_score -= self.score_candidates[idx]["score"]
            for i in range(7):
                self.dice_point_counts[i] += removed_dices.count(i)

    def generate_message(self):
        number_emojis: list[str] = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        resp = ""
        assert self.game.current_player is not None
        current_player = self.game.current_player
        resp += f"【{current_player.member.mention}】投出了: `{', '.join(str(d) for d in self.roll)}`\n\n"
        for i, candidate in enumerate(self.score_candidates):
            score = candidate["score"]
            remove = ', '.join([str(r) for r in candidate["remove"]])
            choice = f"{number_emojis[i]} 移除骰子 [{remove}], 得分 {score}"
            if candidate["is_selected"]:
                choice = f"- ~~*{choice}*~~"
            else:
                choice = f"- {choice}"
            resp += f"{choice}\n"
        resp += f"\n当前总得分: {current_player.score}\n"
        resp += f"本轮临时积分: {self.turn_score}\n"
        resp += f"当前临时积分: {self.roll_score}\n"

        alerts = self._generate_alert()
        resp += alerts
        return resp

    def _generate_alert(self) -> str:
        alert = ""
        if not self.score_candidates:
            alert += "⚠️ 本轮未得分，跳过回合！\n"
        elif any([i < 0 for i in self.dice_point_counts]):
            alert += "⚠️ 你已经选择了超过可用骰子的得分方案，请调整选择。"
            if self.roll_score == 0:
                alert += "⚠️ 你需要至少选择一项得分方案。"
        if alert:
            return "```\n" + alert + "\n```"
        else:
            return ""


class RollView(discord.ui.View):
    def __init__(self, dispatcher: Dispatcher, roll: Turn, choice_count: int, target_user_id: int):
        super().__init__(timeout=None)
        self.dispatcher = dispatcher
        self.target_user_id = target_user_id
        self.idx_buttons = []
        self.create_buttons(choice_count)
        self.roll = roll
        self.dispatcher.on(RollSignal.SELECTION_UPDATED.value, self.on_selection_updated)
        self.message: Message | None = None

    async def disable_all(self):
        if not self.message:
            return
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def disable_buttons(self, interaction: Interaction):
        message = interaction.message
        if message:
            await message.edit(view=None)

    def get_button_by_id(self, custom_id: str) -> discord.ui.Button | None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == custom_id:
                return child
        return None

    def get_button_by_label(self, label: str) -> discord.ui.Button | None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == label:
                return child
        return None

    async def on_selection_updated(self, interaction: Interaction):
        for idx, cand in enumerate(self.roll.score_candidates):
            # button = self.get_button_by_label(f"{idx + 1}")
            button = self.idx_buttons[idx]
            if button and cand["is_selected"]:
                button.style = discord.ButtonStyle.primary
            elif button and not cand["is_selected"]:
                button.style = discord.ButtonStyle.secondary
        assert interaction.message is not None
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            view=self
        )

    def create_buttons(self, choice_count: int):
        self.clear_items()
        # create choice buttons
        for idx in range(choice_count):
            button = discord.ui.Button(label=f"{idx + 1}", style=discord.ButtonStyle.secondary)
            button.callback = self._select_choice_callback(idx)
            self.idx_buttons.append(button)
            self.add_item(button)
            # self.add_item(self._create_choice_button(idx))

        # select button
        self.add_item(self._create_select_button())
        # confirm button
        self.add_item(self._create_confirm_button())

    async def interaction_check(self, interaction: Interaction) -> bool:
        """检查用户是否是允许操作的指定用户"""
        if interaction.user.id == self.target_user_id:
            # 如果是指定用户，允许继续执行按钮回调
            return True
        else:
            # 如果不是指定用户，发送一条私密（ephemeral）警告消息
            await interaction.response.send_message("不是你的回合。", ephemeral=True)
            # 阻止按钮回调的执行
            return False

    def _select_choice_callback(self, idx: int):
        async def callback(interaction: Interaction):
            await self.dispatcher.emit(RollSignal.CHOICE_CLICKED.value[idx], interaction, idx)
        return callback

    # def _create_choice_button(self, idx: int) -> discord.ui.Button:
    #     button = discord.ui.Button(label=f"{idx + 1}", style=discord.ButtonStyle.secondary)
    #     button.callback = self._select_choice_callback(idx, button)
    #     return button

    def _next_roll(self):
        async def callback(interaction: Interaction):
            await self.dispatcher.emit(RollSignal.NEXT_ROLL_BUTTON_CLICKED.value, interaction)
        return callback

    def _create_select_button(self) -> discord.ui.Button:
        button = discord.ui.Button(label="确定回合", style=discord.ButtonStyle.primary)
        button.callback = self._next_roll()
        return button

    def _sumbmit_score(self):
        async def callback(interaction: Interaction):
            await self.dispatcher.emit(RollSignal.SCORE_SUBMITED.value, interaction)
        return callback

    def _create_confirm_button(self) -> discord.ui.Button:
        button = discord.ui.Button(label="✅", style=discord.ButtonStyle.success)
        button.callback = self._sumbmit_score()
        return button
