from community import Member, Community


def player_score(community: Community) -> list[int]:
    """
    Calculate the score of every player sort from best to worst
    """
    members = {member.id: 0 for member in community.members}

    for member in community.members:
        if member.energy <= -10:
            continue
        for task in community.tasks:
            cost = sum(
                max(task[i] - member.abilities[i], 0)
                for i in range(len(member.abilities))
            )
            members[member.id] += cost

    return sorted(members, key=members.get)


def sacrifice(player: Member, community: Community):
    """
    Sacrifice the weakest community member, only when
    all tasks are impossible and when no other task can be done
    """
    members = player_score(community)

    if player.id != members[-1] or len(community.tasks) == 0:
        return []

    impossible_tasks = []

    # NOTE: Sacrificing is a last resort and has negative impact on community performance
    #       Thus, only consider sacrificying a player if a task cannot be completed by any
    #       pair with full energy.
    full_energy = 10

    for idx, task in enumerate(community.tasks):
        for p1 in community.members:
            for p2 in community.members:
                if p1 == p2:
                    continue

                energy_cost = (
                    sum(
                        max(task[i] - max(p1.abilities[i], p2.abilities[i]), 0)
                        for i in range(len(player.abilities))
                    )
                    * 0.5
                )

                if full_energy - energy_cost > -10:
                    return []

        impossible_tasks.append(idx)

    return [impossible_tasks[0]]


def calculate_minimum_delta_pair(
    player: Member, best_partner: int, community: Community
):
    """
    Find the best task for a pair, the task that minimizes suitability + energy

    delta = min(energy + suitability)
    """
    members = {member.id: member for member in community.members}
    partner = members[best_partner]
    num_abilities = len(player.abilities)

    minimum_delta = float("inf")
    best_task = 0
    best_pair_cost = 0

    for task_index, task in enumerate(community.tasks):
        pair_cost = (
            sum(
                max(task[i] - max(player.abilities[i], partner.abilities[i]), 0)
                for i in range(num_abilities)
            )
            * 0.5
        )
        pair_suitability = (
            sum(
                abs(max(player.abilities[i], partner.abilities[i]) - task[i])
                for i in range(num_abilities)
            )
            * 0.5
        )

        if minimum_delta >= pair_cost + pair_suitability:
            minimum_delta = pair_cost + pair_suitability
            best_task = task_index
            best_pair_cost = pair_cost

    return (best_task, best_pair_cost, minimum_delta)


def phaseIpreferences(player: Member, community: Community, global_random):
    """
    Return a list of task index and the partner id for the particular player. The output
    format should be a list of lists such that each element in the list has the first index
    task [index in the community.tasks list] and the second index as the partner id
    """
    list_choices = []

    if player.energy < 2:
        return list_choices

    # Members are stored from best to worst (best player index: 0)
    members = player_score(community)

    for partner in members:
        if partner == player.id:
            continue

        task, pair_cost, pair_delta = calculate_minimum_delta_pair(
            player, partner, community
        )

        player_cost = sum(
            max(community.tasks[task][i] - player.abilities[i], 0)
            for i in range(len(player.abilities))
        )

        player_suitability = (
            sum(
                abs(player.abilities[i] - community.tasks[task][i])
                for i in range(len(player.abilities))
            )
            * 0.25
        )

        player_delta = player_cost + player_suitability

        # Energy management (players don't kill themselves)
        if pair_cost >= player.energy + community.members[partner].energy:
            continue

        # Only pair up if it is more benificial
        if pair_delta <= player_delta:
            list_choices.append([task, partner, pair_delta])

    list_choices.sort(key=lambda x: x[2])
    return [[l[0], l[1]] for l in list_choices[:5]]


def phaseIIpreferences(player, community, global_random):
    """Return a list of tasks for the particular player to do individually"""
    if impossible := sacrifice(player, community):
        return impossible

    bids = []
    free_tasks = []
    num_abilities = len(player.abilities)

    for idx, task in enumerate(community.tasks):
        player_cost = sum(
            max(task[i] - player.abilities[i], 0) for i in range(num_abilities)
        )

        player_suitability = (
            sum(abs(player.abilities[i] - task[i]) for i in range(num_abilities)) * 0.25
        )

        if player_cost <= player.energy * 0.7:
            bids.append((idx, player_cost + player_suitability, player_cost))

        if player_cost == 0:
            free_tasks.append(idx)

    # Sort bids by energy and suitability, then cost
    bids.sort(key=lambda x: (x[1], x[2]))
    tasks = [b[0] for b in bids[:3]] + free_tasks
    return tasks
