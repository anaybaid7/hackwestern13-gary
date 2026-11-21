"""Quest choice (issue #21): short or long picks the active quest."""
from conftest import post, quest, sniff, state_of


def scout_posts(client, *quests):
    out = client.post("/api/quests", json={"quests": list(quests)}).json()
    assert out["rejected"] == [], out
    return out


def choose(client, time):
    reply = client.post("/api/quest/choose", json={"time": time})
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_no_choice_yet_shows_the_oldest_open_quest(client):
    state = state_of(client)
    assert state["quest"]["id"] == "q-demo-bottle" and state["quest_choice"] is None
    assert state["quest_options"]["short"]["id"] == "q-demo-bottle"
    assert state["quest_options"]["long"]["id"] == "q-harris-bench"


def test_choosing_takes_todays_scout_quests_first(client):
    scout_posts(client,
                quest("q-old", "bird", "Kains Woods", day="2026-11-19"),            # the scout, two days ago
                quest("q-today-1", "bench", "Gibbons Park"),                        # the scout, today
                quest("q-today-2", "dog", "Springbank Park"))
    out = choose(client, "short")
    assert out["quest"]["id"] == "q-today-1", "today's scout quest beats the seed quest and the old one"
    assert out["state"]["quest"]["id"] == "q-today-1" and out["state"]["quest_choice"] == "short"
    assert state_of(client) == out["state"], "the reply carries the new state"
    # the other button still shows what it would give
    assert out["state"]["quest_options"]["long"]["id"] == "q-harris-bench"
    assert out["state"]["quest_options"]["short"]["id"] == "q-today-1"


def test_asking_again_moves_to_the_next_quest_and_wraps(client):
    scout_posts(client, quest("q-a", "bench", "Gibbons Park"), quest("q-b", "dog", "Springbank Park"))
    seen = [choose(client, "short")["quest"]["id"] for _ in range(5)]
    # today's scout quests, then today's seed quests, then round again
    assert seen == ["q-a", "q-b", "q-demo-bottle", "q-demo-backpack", "q-a"], seen
    assert choose(client, "long")["quest"]["id"] == "q-harris-bench"
    assert choose(client, "long")["quest"]["id"] == "q-harris-bench", "only one long quest: it stays"


def test_no_quest_of_that_length_changes_nothing(client):
    post(client, sniff("bench"))                      # finishes the only long quest
    before = state_of(client)
    out = choose(client, "long")
    assert out["quest"] is None and out["state"] == before
    assert client.post("/api/quest/choose", json={"time": "medium"}).status_code == 422
    assert client.post("/api/quest/choose", json={}).status_code == 422


def test_the_device_gets_the_active_quest_first(client):
    scout_posts(client, quest("q-a", "bench", "Gibbons Park"), quest("q-b", "dog", "Springbank Park"))
    before = [q["id"] for q in client.get("/api/quests").json()["quests"]]
    assert before == ["q-demo-bottle", "q-demo-backpack", "q-harris-bench", "q-a", "q-b"]
    choose(client, "short")
    choose(client, "short")                           # now q-b
    quests = client.get("/api/quests").json()["quests"]
    assert [q["id"] for q in quests] == ["q-b", "q-demo-bottle", "q-demo-backpack", "q-harris-bench", "q-a"]
    assert [q["active"] for q in quests] == [True, False, False, False, False]
    assert [q["id"] for q in client.get("/api/quests?time=long").json()["quests"]] == ["q-harris-bench"]


def test_the_chosen_quest_wins_when_two_quests_want_the_same_thing(client, clock):
    scout_posts(client, quest("q-gibbons", "bench", "Gibbons Park"), quest("q-springbank", "bench", "Springbank Park"))
    choose(client, "short")
    assert choose(client, "short")["quest"]["id"] == "q-springbank"
    clock.forward(minutes=20)
    # The device was offline and still names the first bench quest in its old list.
    out = post(client, sniff("bench", quest_id="q-gibbons", ts="2026-11-21T05:40:00Z"))
    assert out["results"][0]["quest_id"] == "q-springbank", "the person said Springbank; that is where they are"
    state = state_of(client)
    assert [t["place"] for t in state["map"] if t["cleared"]] == ["Springbank Park"]
    assert state["journal"][0]["place"] == "Springbank Park"
    # the card moves on to the next short quest
    assert state["quest"]["id"] == "q-gibbons" and state["quest_choice"] == "short"


def test_a_later_choice_never_rewrites_what_an_earlier_sniff_finished(client, clock):
    scout_posts(client, quest("q-gibbons", "bench", "Gibbons Park"), quest("q-springbank", "bench", "Springbank Park"))
    choose(client, "short")                                           # Gibbons
    clock.forward(minutes=10)
    post(client, sniff("bench", ts="2026-11-21T05:30:00Z"))
    clock.forward(minutes=10)
    assert state_of(client)["quest"]["id"] == "q-springbank", "the card moved on by itself"
    choose(client, "short")                                           # "another one": past Springbank
    clock.forward(minutes=10)
    state = state_of(client)
    assert [t["place"] for t in state["map"] if t["cleared"]] == ["Gibbons Park"], "history stays as it happened"
    assert state["quest"]["id"] == "q-demo-bottle"


def test_a_sniff_made_before_the_choice_but_uploaded_after_it(client, clock):
    """The device was offline: the sniff happened at 5:10, the choice at 5:22, the upload at 5:32."""
    scout_posts(client, quest("q-gibbons", "bench", "Gibbons Park"), quest("q-springbank", "bench", "Springbank Park"))
    choose(client, "short")
    choose(client, "short")                                           # Springbank, chosen at 5:22
    clock.forward(minutes=10)
    out = post(client, sniff("bench", quest_id="q-gibbons", ts="2026-11-21T05:10:00Z"))
    assert out["results"][0]["quest_id"] == "q-gibbons", "at 5:10 nothing was chosen, so the device's word stands"


def test_with_no_choice_the_devices_named_quest_wins(client):
    scout_posts(client, quest("q-gibbons", "bench", "Gibbons Park"))
    # two open bench quests: the seed one at Harris Park is older
    assert post(client, sniff("bench", quest_id="q-gibbons"))["results"][0]["quest_id"] == "q-gibbons"
    assert post(client, sniff("bench"))["results"][0]["quest_id"] == "q-harris-bench"


def test_other_quests_still_complete_while_one_is_active(client):
    """Forgiving on purpose: the card shows one quest, but any open quest whose
    thing Gary names is finished. The demo's two table quests rely on it."""
    scout_posts(client, quest("q-gibbons", "bench", "Gibbons Park"))
    assert choose(client, "short")["quest"]["id"] == "q-gibbons"
    out = post(client, sniff("bottle"), sniff("backpack", friend=True))
    assert [r["quest_id"] for r in out["results"]] == ["q-demo-bottle", "q-demo-backpack"]
    assert state_of(client)["quest"]["id"] == "q-gibbons", "the chosen quest stays on the card"


def test_a_herd_quest_can_be_chosen_and_then_skipped(client):
    post(client, sniff("bottle"))
    assert choose(client, "short")["quest"]["id"] == "q-demo-backpack"      # needs a friend
    assert state_of(client)["herd"]["quest"]["id"] == "q-demo-backpack"
    post(client, sniff("backpack"))                                          # alone: found, not completed
    assert state_of(client)["quest"]["id"] == "q-demo-backpack"
    post(client, sniff("backpack", friend=True))
    state = state_of(client)
    assert state["herd"]["quest"] is None and state["quest"]["id"] == "q-harris-bench"
