from app.projects.codenames_online.game_logic import remaining_counts
from app.projects.codenames_online.models import CodenamesOnlineRoom
from app.projects.codenames_online.word_lists import list_word_lists


def _tile_colors_for_guesser(words, key, revealed):
    colors = []
    for idx, _word in enumerate(words or []):
        if revealed and revealed[idx]:
            colors.append(key[idx])
        else:
            colors.append(None)
    return colors


def _can_show_board(room, viewer_seat):
    if room.status in (CodenamesOnlineRoom.STATUS_ACTIVE, CodenamesOnlineRoom.STATUS_WON):
        return True
    if room.status == CodenamesOnlineRoom.STATUS_PREVIEW:
        return (
            viewer_seat is not None
            and room.phone_role_for_seat(viewer_seat)
            == CodenamesOnlineRoom.ROLE_CLUE_GIVER
        )
    return False


def room_to_dict(room, viewer_seat, is_admin=False):
    clue_seat = room.clue_giver_seat()
    guesser_seat = room.guesser_seat()
    phone_role = room.phone_role_for_seat(viewer_seat) if viewer_seat else None

    payload = {
        "code": room.code,
        "status": room.status,
        "turn": room.turn,
        "winner": room.winner,
        "seats": {
            "X": room.seat_x is not None,
            "O": room.seat_o is not None,
        },
        "phone_roles": {
            "X": room.phone_role_x,
            "O": room.phone_role_o,
        },
        "your_seat": viewer_seat,
        "your_phone_role": phone_role,
        "name_red": room.name_red,
        "name_blue": room.name_blue,
        "word_list_id": room.word_list_id,
        "exclude_confusing": room.exclude_confusing,
        "word_lists": list_word_lists(),
        "version": room.version,
        "is_admin": bool(is_admin),
        "can_boot": bool(
            is_admin
            and phone_role == CodenamesOnlineRoom.ROLE_CLUE_GIVER
            and room.status == CodenamesOnlineRoom.STATUS_PREVIEW
        ),
        "clue_giver_seat": clue_seat,
        "guesser_seat": guesser_seat,
    }

    if viewer_seat is None:
        payload["spectator"] = True

    if phone_role == CodenamesOnlineRoom.ROLE_CLUE_GIVER and room.status in (
        CodenamesOnlineRoom.STATUS_WAITING_START,
        CodenamesOnlineRoom.STATUS_PREVIEW,
        CodenamesOnlineRoom.STATUS_WON,
    ):
        payload["setup_allowed"] = True

    if _can_show_board(room, viewer_seat):
        payload["words"] = room.words
        payload["revealed"] = room.revealed or [False] * 25

        if phone_role == CodenamesOnlineRoom.ROLE_CLUE_GIVER or (
            viewer_seat is None and room.status == CodenamesOnlineRoom.STATUS_WON
        ):
            payload["key"] = room.key
            payload["remaining"] = remaining_counts(room.key, room.revealed)
        elif phone_role == CodenamesOnlineRoom.ROLE_GUESSER or viewer_seat is None:
            payload["tile_colors"] = _tile_colors_for_guesser(
                room.words, room.key, room.revealed
            )

    if room.turn and room.status in (
        CodenamesOnlineRoom.STATUS_PREVIEW,
        CodenamesOnlineRoom.STATUS_ACTIVE,
    ):
        payload["turn_spymaster"] = room.spymaster_name(room.turn)

    if room.winner:
        payload["winner_spymaster"] = room.spymaster_name(room.winner)

    return payload
