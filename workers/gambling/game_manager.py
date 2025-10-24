import discord
from discord import Interaction, Message
from discord.ext import commands

from workers.gambling.dispatcher import Dispatcher
from workers.gambling.game import RollView, Turn
from workers.gambling.signals import NewGameSignal, RollSignal
from workers.gambling.game import Game


class GameView(discord.ui.View):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__(timeout=None)
        self.dispatcher = dispatcher
        self.message: Message | None = None

    async def disable_all(self):
        if not self.message:
            return
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="加入游戏", style=discord.ButtonStyle.primary)
    async def join_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.dispatcher.emit(NewGameSignal.JOIN_BUTTON_CLICKED.value, interaction)

    @discord.ui.button(label="开始游戏", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.dispatcher.emit(NewGameSignal.START_BUTTON_CLICKED.value, interaction)


class GameDealer:
    def __init__(self, dispatcher: Dispatcher, interaction: Interaction):
        # NewGameSignal handlers
        dispatcher.on(NewGameSignal.JOIN_BUTTON_CLICKED.value, self.on_join_button_clicked)
        dispatcher.on(NewGameSignal.START_BUTTON_CLICKED.value, self.on_start_button_clicked)

        # RollSignal handlers
        for dispatcher_event in RollSignal.CHOICE_CLICKED.value:
            dispatcher.on(dispatcher_event, self.on_select_choice_button_clicked)
        dispatcher.on(RollSignal.NEXT_ROLL_BUTTON_CLICKED.value, self.on_next_roll_button_clicked)
        dispatcher.on(RollSignal.SCORE_SUBMITED.value, self.on_score_submited)

        self.dispatcher = dispatcher
        self.interaction = interaction
        self.game = Game()
        self.roll = None
        self.active_views = []

    # NewGameSignal handlers
    async def on_join_button_clicked(self, click_interaction: Interaction):
        await click_interaction.response.defer()
        click_user = click_interaction.user

        # logic to add or remove player
        if not self.game.is_player_in(click_user):
            self.game.add_player(click_user)
        else:
            self.game.remove_player(click_user)

        # update message content
        content = self.game.generate_message_content()
        assert click_interaction.message is not None
        await click_interaction.followup.edit_message(
            message_id=click_interaction.message.id,
            content=content
        )

    # RollSignal handlers
    async def on_start_button_clicked(self, click_interaction: Interaction):
        await click_interaction.response.defer()
        await self.next_roll(click_interaction, next_player=True)

    async def on_next_roll_button_clicked(self, click_interaction: Interaction):
        await click_interaction.response.defer()
        await self.next_roll(click_interaction, next_player=False)

    async def on_score_submited(self, click_interaction: Interaction):
        await click_interaction.response.defer()
        await self.next_roll(click_interaction, next_player=True)

    async def on_select_choice_button_clicked(self, click_interaction: Interaction, idx):
        await click_interaction.response.defer()
        if not self.roll:
            return
        self.roll.update_selection(idx)
        content = self.roll.generate_message()
        assert click_interaction.message is not None
        await click_interaction.followup.edit_message(
            message_id=click_interaction.message.id,
            content=content
        )
        # await self.dispatcher.emit(RollSignal.SELECTION_UPDATED.value, click_interaction)

    async def update_message(self, interaction: Interaction):
        assert self.roll is not None
        content = self.roll.generate_message()
        assert interaction.message is not None
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            content=content
        )

    async def disable_views(self):
        for view in self.active_views:
            await view.disable_all()
        self.active_views.clear()

    async def send_message(self, interaction: Interaction):
        assert self.roll is not None
        assert self.game.current_player is not None
        await self.disable_views()
        view = RollView(
            self.dispatcher,
            self.roll,
            len(self.roll.score_candidates),
            self.game.current_player.member.id
        )
        content = self.roll.generate_message()
        view.message = await interaction.channel.send(content=content, view=view)
        self.active_views.append(view)

    async def next_roll(self, click_interaction: Interaction, next_player: bool):
        # check player count
        if self.game.player_count < 2:
            content = self.game.generate_message_content()
            content += "```\n至少需要两名玩家才能开始游戏！\n```*"
            assert click_interaction.message is not None
            await click_interaction.followup.edit_message(
                message_id=click_interaction.message.id,
                content=content
            )
            return

        # next roll for the same player
        if self.roll and self.roll.is_ok_to_submit() and not next_player:
            self.roll.finish()
            self.roll.roll_dice()
            assert self.game.current_player is not None
            await self.send_message(click_interaction)

        # next roll for the next player
        if self.roll and self.roll.is_ok_to_submit() and next_player:
            # update current message
            self.roll.finish()
            self.roll.submit_score()
            await self.update_message(click_interaction)
            if self.roll.game.winner:
                await self.roll.game.end_game(click_interaction)
                return

            # new message
            self.game.next_player()
            self.roll = Turn(self.game, self.dispatcher)
            await self.send_message(click_interaction)

        # first roll
        if not self.roll or not self.game.current_player:
            self.game.next_player()
            self.roll = Turn(self.game, self.dispatcher)
            await self.send_message(click_interaction)

        # failed
        if self.roll.is_failed and next_player:
            self.game.next_player()
            self.roll = Turn(self.game, self.dispatcher)
            await self.send_message(click_interaction)

        # failed agail
        if self.roll.is_failed:
            await self.next_roll(click_interaction, next_player=True)


class GambleManager(commands.Cog):
    def __init__(self):
        self.games = {}

    async def new_game(self, interaction: Interaction):
        # clean empty games
        await interaction.response.defer()
        assert interaction.channel is not None
        self.games = {c: g for c, g in self.games.items() if g.game.players}
        dispatcher = Dispatcher()
        game_dealer = GameDealer(dispatcher, interaction)
        self.games[interaction.channel.id] = game_dealer
        view = GameView(dispatcher)

        content = game_dealer.game.generate_message_content()
        view.message = await interaction.followup.send(content=content, view=view)
        game_dealer.active_views.append(view)

    async def run(self, interaction: Interaction):
        await self.new_game(interaction)
