from rich_click.rich_group import RichGroup


class AppearanceOrderGroup(RichGroup):
    """
    Sort commands by order of appearance.
    """

    def list_commands(self, ctx):
        return self.commands.keys()
