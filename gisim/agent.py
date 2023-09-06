"""Player & agent APIs
"""
from abc import ABC
from collections import Counter
from typing import Dict, List, Iterator

from gisim.cards.characters import get_character_card
from gisim.classes.action import (
    Action,
    ChangeCardsAction,
    ChangeCharacterAction,
    DeclareEndAction,
    RollDiceAction,
    UseCardAction,
    UseSkillAction,
)
from gisim.classes.enums import (
    CharPos,
    ElementType,
    EntityType,
    GamePhase,
    GameStatus,
    PlayerID,
    SkillType,
)
from gisim.game import GameInfo


class Agent(ABC):
    def __init__(self, player_id: PlayerID):
        self.player_id = player_id

    def take_action(self, game_info: GameInfo) -> Action:
        raise NotImplementedError


class SimpleAgent(ABC):
    def take_action(self, game_info: GameInfo) -> Action:
        if game_info.status == GameStatus.INITIALIZING:
            if game_info.phase == GamePhase.CHANGE_CARD:
                return self.take_action_on_init_change_card(game_info)

            elif game_info.phase == GamePhase.SELECT_ACTIVE_CHARACTER:
                return self.take_action_on_init_select_character(game_info)

        elif game_info.status == GameStatus.RUNNING:
            if game_info.phase == GamePhase.ROLL_DICE:
                return self.take_action_on_roll_dice(game_info)

            elif game_info.phase == GamePhase.PLAY_CARDS:
                return self.take_action_on_play_cards(game_info)

            elif game_info.phase == GamePhase.ROUND_END:
                return self.take_action_on_round_end(game_info)

        return DeclareEndAction()

    def take_action_on_init_change_card(self, game_info: GameInfo):
        # default behaviour: do nothing
        _ = game_info
        return ChangeCardsAction(cards_idx=[])

    def take_action_on_init_select_character(self, game_info: GameInfo):
        # default behaviour: push the middle one up
        _ = game_info
        return ChangeCharacterAction(position=CharPos.MIDDLE, dice_idx=[])

    def take_action_on_roll_dice(self, game_info: GameInfo):
        # default behaviour: use the current activate character's element
        player_info = game_info.get_player_info()
        current_character = player_info.characters[player_info.active_character_position]
        character_card = get_character_card(current_character.character.name)
        character_element = character_card.element_type
        current_dice = player_info.dice_zone
        reroll_dice_idx = []
        for k, element_type in enumerate(current_dice):
            if element_type not in [character_element, ElementType.OMNI]:
                reroll_dice_idx.append(k)
        return RollDiceAction(dice_idx=reroll_dice_idx)

    def take_action_on_play_cards(self, game_info: GameInfo):
        raise NotImplementedError

    def take_action_on_round_end(self, game_info: GameInfo):
        # default behaviour: change character when the current one is down
        player_info = game_info.get_player_info()
        active_pos = player_info.active_character_position
        character_info = player_info.characters[active_pos.value]
        if character_info.character.health_point <= 0:
            alive_positions = [
                CharPos(k)
                for k, character in enumerate(player_info.characters)
                if character.character.alive
            ]
            return ChangeCharacterAction(
                position=alive_positions[0], dice_idx=[]
            )

        return DeclareEndAction()


class NoActionAssigned(Exception):
    pass


class MultipleActionAgent(Agent):
    def __init__(self, player_id: PlayerID):
        Agent.__init__(self, player_id)
        self._current_iter = None

    def take_multiple_actions(self, game_info: GameInfo) -> Iterator[Action]:
        raise NotImplementedError

    def take_action(self, game_info: GameInfo) -> Action:
        try:
            if self._current_iter is None:
                raise StopIteration

            return next(self._current_iter)
        except StopIteration:

            self._current_iter = self.take_multiple_actions(game_info)
            try:
                return next(self._current_iter)
            except StopIteration:
                raise NoActionAssigned(f'No action assigned for {game_info!r}. '
                                       f'Please check the implementation of '
                                       f'{self.__class__.__name__}.take_multiple_action')


class GenericMultipleAction(MultipleActionAgent):
    def yield_actions_on_init_change_card(self, game_info: GameInfo) -> Iterator[Action]:
        # default behaviour: do nothing
        _ = game_info
        yield ChangeCardsAction(cards_idx=[])

    def yield_actions_on_init_select_character(self, game_info: GameInfo) -> Iterator[Action]:
        # default behaviour: push the middle one up
        _ = game_info
        yield ChangeCharacterAction(position=CharPos.MIDDLE, dice_idx=[])

    def yield_actions_on_roll_dice(self, game_info: GameInfo) -> Iterator[Action]:
        # default behaviour: use the current activate character's element
        player_info = game_info.get_player_info()
        current_character = player_info.characters[player_info.active_character_position]
        character_card = get_character_card(current_character.character.name)
        character_element = character_card.element_type
        current_dice = player_info.dice_zone
        reroll_dice_idx = []
        for k, element_type in enumerate(current_dice):
            if element_type not in [character_element, ElementType.OMNI]:
                reroll_dice_idx.append(k)
        yield RollDiceAction(dice_idx=reroll_dice_idx)

    def yield_actions_on_play_cards(self, game_info: GameInfo) -> Iterator[Action]:
        raise NotImplementedError

    def yield_actions_on_round_end(self, game_info: GameInfo) -> Iterator[Action]:
        # default behaviour: change character when the current one is down
        player_info = game_info.get_player_info()
        active_pos = player_info.active_character_position
        character_info = player_info.characters[active_pos.value]
        if character_info.character.health_point <= 0:
            alive_positions = [
                CharPos(k)
                for k, character in enumerate(player_info.characters)
                if character.character.alive
            ]
            yield ChangeCharacterAction(
                position=alive_positions[0], dice_idx=[]
            )
        else:
            yield DeclareEndAction()

    def take_multiple_actions(self, game_info: GameInfo) -> Iterator[Action]:
        if game_info.status == GameStatus.INITIALIZING:
            if game_info.phase == GamePhase.CHANGE_CARD:
                yield from self.yield_actions_on_init_change_card(game_info)
                return

            elif game_info.phase == GamePhase.SELECT_ACTIVE_CHARACTER:
                yield from self.yield_actions_on_init_select_character(game_info)
                return

        elif game_info.status == GameStatus.RUNNING:
            if game_info.phase == GamePhase.ROLL_DICE:
                yield from self.yield_actions_on_roll_dice(game_info)
                return

            elif game_info.phase == GamePhase.PLAY_CARDS:
                yield from self.yield_actions_on_play_cards(game_info)
                return

            elif game_info.phase == GamePhase.ROUND_END:
                yield from self.yield_actions_on_round_end(game_info)
                return

        yield DeclareEndAction()


class AttackOnlyAgent(SimpleAgent):
    def __init__(self, player_id: PlayerID):
        super().__init__(player_id)

    def get_dice_idx_greedy(
            self,
            dice: List[ElementType],
            cost: Dict[ElementType, int],
            char_element: ElementType = ElementType.NONE,
    ):
        # First determine whether the current dice are enough
        dice_idx = []
        used = [False for _ in dice]
        for key, val in cost.items():
            remaining = val
            if 1 <= key.value <= 7:
                # 7 majors elements
                remaining = val
                for idx, die in enumerate(dice):
                    if used[idx]:
                        continue
                    if idx not in dice_idx and die == key:
                        remaining -= 1
                        dice_idx.append(idx)
                        used[idx] = True
                        if remaining == 0:
                            break
                if remaining > 0:
                    # Need to take OMNI elements
                    for idx, die in enumerate(dice):
                        if used[idx]:
                            continue
                        if idx not in dice_idx and die == ElementType.OMNI:
                            remaining -= 1
                            dice_idx.append(idx)
                            used[idx] = True
                            if remaining == 0:
                                break
                if remaining > 0:
                    # Insufficient dice
                    return []
            elif key == ElementType.ANY:
                # Arbitrary element
                for idx, die in enumerate(dice):
                    if used[idx]:
                        continue
                    if idx not in dice_idx and die != char_element:
                        remaining -= 1
                        dice_idx.append(idx)
                        used[idx] = True
                        if remaining == 0:
                            break
                if remaining > 0:
                    # Insufficient unaligned dice: we first use the dice with character element
                    for idx, die in enumerate(dice):
                        if used[idx]:
                            continue
                        if idx not in dice_idx and die == char_element:
                            remaining -= 1
                            dice_idx.append(idx)
                            used[idx] = True
                            if remaining == 0:
                                break
                if remaining > 0:
                    # Insufficient unaligned dice: we first use the dice with character element
                    for idx, die in enumerate(dice):
                        if used[idx]:
                            continue
                        if idx not in dice_idx and die == ElementType.OMNI:
                            remaining -= 1
                            dice_idx.append(idx)
                            used[idx] = True
                            if remaining == 0:
                                break
                if remaining > 0:
                    return []
            elif key == ElementType.SAME:
                dice_counter = Counter(
                    [dice[idx] for idx, die_used in enumerate(used) if not die_used]
                )
                if ElementType.OMNI not in dice_counter.keys():
                    dice_counter[ElementType.OMNI] = 0
                if char_element not in dice_counter.keys():
                    dice_counter[char_element] = 0
                sorted_counter = dict(
                    sorted(dice_counter.items(), key=lambda item: item[1])
                )
                satisfied = False
                for element, cnt in sorted_counter.items():
                    if element in [ElementType.OMNI, char_element]:
                        continue
                    if cnt >= val:
                        for idx, die in enumerate(dice):
                            if used[idx]:
                                continue
                            if element == die:
                                used[idx] = True
                                dice_idx.append(idx)
                                remaining -= 1
                                if remaining == 0:
                                    break
                        satisfied = True
                        break
                if satisfied:
                    continue
                omni_count = sorted_counter[ElementType.OMNI]
                sorted_counter = dict(
                    sorted(dice_counter.items(), key=lambda item: item[1], reverse=True)
                )
                for element, cnt in sorted_counter.items():
                    if element in [ElementType.OMNI, char_element]:
                        continue
                    if omni_count + cnt >= val:
                        other_remaining = cnt
                        omni_remaining = val - cnt
                        for idx, die in enumerate(dice):
                            if used[idx]:
                                continue
                            if element == die:
                                other_remaining -= 1
                                used[idx] = True
                                dice_idx.append(idx)
                            elif omni_remaining > 0 and die == ElementType.OMNI:
                                omni_remaining -= 1
                                used[idx] = True
                                dice_idx.append(idx)
                        if other_remaining == 0 and omni_remaining == 0:
                            satisfied = True
                            break
                    break
                if satisfied:
                    continue
                char_elem_count = dice_counter[char_element]
                if char_elem_count + omni_count >= val:
                    char_elem_remaining = min(char_elem_count, val)
                    omni_remaining = val - char_elem_remaining
                    for idx, die in enumerate(dice):
                        if used[idx]:
                            continue
                        if char_element == die:
                            char_elem_remaining -= 1
                            used[idx] = True
                            dice_idx.append(idx)
                        elif omni_remaining > 0 and die == ElementType.OMNI:
                            omni_remaining -= 1
                            used[idx] = True
                            dice_idx.append(idx)
                        if char_elem_remaining == 0 and omni_remaining == 0:
                            satisfied = True
                            break
                if not satisfied:
                    return []

        return dice_idx

    def take_action_on_play_cards(self, game_info: GameInfo):
        player_info = game_info.get_player_info()
        active_pos = player_info.active_character_position
        character_info = player_info.characters[active_pos.value]
        character_card = get_character_card(character_info.character.name)
        if character_info.character.health_point <= 0:
            alive_positions = [
                CharPos(k)
                for k, character in enumerate(player_info.characters)
                if character.character.alive
            ]
            return ChangeCharacterAction(
                position=alive_positions[0], dice_idx=[]
            )
        character_element = character_card.element_type
        current_dice = player_info.dice_zone
        skill_names = [skill.name for skill in character_card.skills]
        elemental_burst = character_card.get_skill(
            skill_type=SkillType.ELEMENTAL_BURST
        )
        skill_name = ""
        dice_idx = []

        # Use the talent card of Kamisato Ayaka if appeared
        if "Kanten Senmyou Blessing" in player_info.hand_cards:
            dice_idx = self.get_dice_idx_greedy(
                current_dice, {ElementType.CRYO: 2}, character_card.element_type
            )
            if len(dice_idx) > 0:
                card_idx = player_info.hand_cards.index(
                    "Kanten Senmyou Blessing"
                )
                return UseCardAction(
                    card_idx=card_idx,
                    card_target=[
                        (self.player_id, EntityType.CHARACTER, active_pos.value)
                    ],
                    dice_idx=dice_idx,
                    card_user_pos=active_pos,
                )
        if "Traveler's Handy Sword" in player_info.hand_cards:
            dice_idx = self.get_dice_idx_greedy(
                current_dice, {ElementType.SAME: 2}, character_card.element_type
            )
            if len(dice_idx) > 0:
                card_idx = player_info.hand_cards.index(
                    "Traveler's Handy Sword"
                )
                return UseCardAction(
                    card_idx=card_idx,
                    card_target=[
                        (self.player_id, EntityType.WEAPON, active_pos.value)
                    ],
                    dice_idx=dice_idx,
                    card_user_pos=active_pos,
                )
        if "Sacrificial Sword" in player_info.hand_cards:
            dice_idx = self.get_dice_idx_greedy(
                current_dice, {ElementType.SAME: 3}, character_card.element_type
            )
            if len(dice_idx) > 0:
                card_idx = player_info.hand_cards.index("Sacrificial Sword")
                return UseCardAction(
                    card_idx=card_idx,
                    card_target=[
                        (self.player_id, EntityType.WEAPON, active_pos.value)
                    ],
                    dice_idx=dice_idx,
                    card_user_pos=active_pos,
                )
        if (
                character_info.character.power
                == elemental_burst.costs[ElementType.POWER]
        ):
            dice_idx = self.get_dice_idx_greedy(
                current_dice, elemental_burst.costs, character_card.element_type
            )
            if len(dice_idx) > 0:
                skill_name = elemental_burst.name
        if not dice_idx:
            # Insufficient power for elemental burst
            elemental_skill = character_card.get_skill(
                skill_type=SkillType.ELEMENTAL_SKILL
            )
            dice_idx = self.get_dice_idx_greedy(
                current_dice, elemental_skill.costs, character_card.element_type
            )
            if len(dice_idx) > 0:
                skill_name = elemental_skill.name
        if not dice_idx:
            # Insufficient dice for elemental skill
            normal_attack = character_card.get_skill(
                skill_type=SkillType.NORMAL_ATTACK
            )
            dice_idx = self.get_dice_idx_greedy(
                current_dice, normal_attack.costs, character_card.element_type
            )
            if len(dice_idx) > 0:
                skill_name = normal_attack.name
        if not dice_idx:
            # No skill applicable
            return DeclareEndAction()
        else:
            return UseSkillAction(
                user_position=active_pos,
                skill_name=skill_name,
                dice_idx=dice_idx,
                skill_targets=[
                    (
                        ~self.player_id,
                        game_info.get_opponent_info().active_character_position,
                    )
                ],
            )


class NoAttackAgent(SimpleAgent):
    def __init__(self, player_id: PlayerID):
        super().__init__(player_id)

    def take_action_on_play_cards(self, game_info: GameInfo):
        return self.take_action_on_round_end(game_info)
