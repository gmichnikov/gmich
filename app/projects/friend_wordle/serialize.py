from app.projects.friend_wordle.room_service import MAX_GUESSES


def _roles(room):
    return {"X": room.role_x, "O": room.role_o}


def _your_role(room, viewer_seat):
    if viewer_seat is None:
        return None
    return room.role_for_seat(viewer_seat)


def _include_secret(room, viewer_seat):
    if room.status in ("won", "lost"):
        return True
    setter = _setter_seat_from_room(room)
    if viewer_seat == setter and room.status in ("setting_word", "guessing"):
        return True
    return False


def _setter_seat_from_room(room):
    if room.role_x == "setter":
        return "X"
    if room.role_o == "setter":
        return "O"
    return None


def room_to_dict(room, viewer_seat):
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

    payload = {
        "code": room.code,
        "status": room.status,
        "roles": _roles(room),
        "your_seat": viewer_seat,
        "your_role": _your_role(room, viewer_seat),
        "your_name": your_name,
        "guesses": room.guesses or [],
        "max_guesses": MAX_GUESSES,
        "seats": {
            "X": room.seat_x is not None,
            "O": room.seat_o is not None,
        },
        "names": {
            "X": room.display_name("X"),
            "O": room.display_name("O"),
        },
        "version": room.version,
    }

    if viewer_seat is None:
        payload["spectator"] = True

    if _include_secret(room, viewer_seat):
        payload["secret"] = room.secret

    return payload
