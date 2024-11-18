def calculate_partnership_cost(player_abilities, partner_abilities, task):
    """Calculate the energy cost for a partnership to complete a task.

    Args:
        player_abilities: List of ability scores for the first player
        partner_abilities: List of ability scores for the second player
        task: List of difficulty levels for the task

    Returns:
        float: The energy cost per player to complete the task as partners
    """
    return (
        sum(
            max(task[i] - max(player_abilities[i], partner_abilities[i]), 0)
            for i in range(len(task))
        )
        / 2
    )


def calculate_task_difficulty(task, community_avg_abilities):
    """Calculate overall task difficulty considering community's average abilities.

    Args:
        task: List of difficulty levels for the task
        community_avg_abilities: List of average ability scores across community

    Returns:
        float: Weighted difficulty score for the task
    """
    difficulty_score = 0
    for difficulty, avg_ability in zip(task, community_avg_abilities):
        # Higher weight for difficulties that exceed community average
        if difficulty > avg_ability:
            difficulty_score += (difficulty - avg_ability) * 1.5
        else:
            difficulty_score += difficulty - avg_ability
    return difficulty_score


def get_community_stats(community):
    """Calculate average abilities and energy levels in the community.

    Args:
        community: Community object containing member information

    Returns:
        tuple: (list of average abilities, average energy level)
    """
    num_members = len(community.members)
    num_abilities = len(community.members[0].abilities)

    avg_abilities = [0] * num_abilities
    total_energy = 0

    for member in community.members:
        for i, ability in enumerate(member.abilities):
            avg_abilities[i] += ability
        total_energy += member.energy

    avg_abilities = [a / num_members for a in avg_abilities]
    avg_energy = total_energy / num_members

    return avg_abilities, avg_energy


def phaseIpreferences(player, community, global_random):
    """Return task-partner preferences for phase I of task assignment.

    Args:
        player: Player object containing id, abilities, and energy
        community: Community object containing tasks and members
        global_random: Random number generator for consistent randomization

    Returns:
        list: List of [task_index, partner_id] pairs representing preferences
    """
    list_choices = []

    # Get community statistics
    community_avg_abilities, community_avg_energy = get_community_stats(community)

    # Skip if energy is too low relative to community average
    if player.energy < max(2, community_avg_energy * 0.25):
        return list_choices

    # Calculate energy reserve needed based on remaining tasks
    tasks_per_player = len(community.tasks) / len(community.members)
    min_energy_reserve = max(1, min(3, tasks_per_player * 0.5))

    # Create potential partnerships dictionary
    partnerships = {}
    for task_index, task in enumerate(community.tasks):
        task_difficulty = calculate_task_difficulty(task, community_avg_abilities)
        partnerships[task_index] = []

        for partner in community.members:
            if partner.id == player.id or partner.energy < min_energy_reserve:
                continue

            energy_cost = calculate_partnership_cost(
                player.abilities, partner.abilities, task
            )

            # Consider partnership only if:
            # 1. Energy cost is manageable for both players
            # 2. Partnership provides significant benefit over working alone
            solo_cost = sum(
                max(task[i] - player.abilities[i], 0) for i in range(len(task))
            )

            if (
                energy_cost
                < min(
                    player.energy - min_energy_reserve,
                    partner.energy - min_energy_reserve,
                )
                and energy_cost < solo_cost * 0.6
            ):

                # Store partnership details with priority score
                priority = (
                    task_difficulty  # Prioritize harder tasks
                    + (10 - energy_cost) * 2  # Prefer efficient partnerships
                    + min(player.energy, partner.energy) * 0.5  # Consider energy levels
                )

                partnerships[task_index].append((partner.id, energy_cost, priority))

    # Sort partnerships by priority and select best options
    for task_index, partner_list in partnerships.items():
        if partner_list:
            # Sort by priority (highest first)
            partner_list.sort(key=lambda x: x[2], reverse=True)
            # Take top 2 options to provide alternatives
            for partner_id, _, _ in partner_list[:2]:
                list_choices.append([task_index, partner_id])

    # Shuffle choices to introduce some randomness while maintaining preference order
    global_random.shuffle(list_choices)

    return list_choices


def calculate_solo_cost(player_abilities, task):
    """Calculate the energy cost for completing a task alone.

    Args:
        player_abilities: List of ability scores for the player
        task: List of difficulty levels for the task

    Returns:
        float: The energy cost to complete the task alone
    """
    return sum(max(task[i] - player_abilities[i], 0) for i in range(len(task)))


def evaluate_task_suitability(player, task, community_avg_abilities):
    """Evaluate how suitable a task is for the player to complete alone.

    Args:
        player: Player object with abilities and energy
        task: List of difficulty levels for the task
        community_avg_abilities: List of average ability scores across community

    Returns:
        tuple: (suitability score, energy cost)
    """
    energy_cost = calculate_solo_cost(player.abilities, task)

    # Calculate how well player's abilities match task requirements
    ability_match = sum(
        1 for i in range(len(task)) if player.abilities[i] >= task[i]
    ) / len(task)

    # Calculate how much better/worse player is compared to community average
    relative_strength = sum(
        player.abilities[i] - community_avg_abilities[i]
        for i in range(len(task))
        if task[i] > 0  # Only consider relevant abilities
    ) / sum(
        1 for t in task if t > 0
    )  # Average over non-zero task requirements

    # Calculate suitability score
    suitability = (
        (10 - energy_cost) * 2  # Prefer tasks with lower energy cost
        + ability_match * 5  # Prefer tasks matching player's abilities
        + relative_strength * 3  # Prefer tasks where player exceeds community average
    )

    return suitability, energy_cost


def get_task_completion_rate(community):
    """Calculate the rate at which tasks are being completed.

    Args:
        community: Community object containing task history

    Returns:
        float: Estimated tasks completed per turn
    """
    # This would need to be implemented based on how task history is stored
    # For now, return a conservative estimate
    return len(community.tasks) / (2 * len(community.members))


def phaseIIpreferences(player, community, global_random):
    """Return task preferences for phase II of task assignment.

    Args:
        player: Player object containing id, abilities, and energy
        community: Community object containing tasks and members
        global_random: Random number generator for consistent randomization

    Returns:
        list: List of task indices representing preferences
    """
    # Get community average abilities
    community_avg_abilities = [
        sum(member.abilities[i] for member in community.members)
        / len(community.members)
        for i in range(len(player.abilities))
    ]

    # Calculate minimum energy reserve based on task completion rate
    completion_rate = get_task_completion_rate(community)
    min_energy_reserve = max(1, min(3, completion_rate))

    # Skip bidding if energy is too low
    if player.energy < min_energy_reserve * 2:
        return []

    # Calculate available energy for tasks
    available_energy = player.energy - min_energy_reserve

    # Evaluate all tasks
    task_evaluations = []
    for i, task in enumerate(community.tasks):
        suitability, energy_cost = evaluate_task_suitability(
            player, task, community_avg_abilities
        )

        # Consider task if:
        # 1. Energy cost is manageable
        # 2. Player has relevant skills (suitability > threshold)
        # 3. Energy cost doesn't exceed available energy
        if (
            energy_cost < available_energy
            and suitability > 0
            and energy_cost <= player.energy * 0.7
        ):  # Don't use more than 70% of energy on one task

            task_evaluations.append((i, suitability, energy_cost))

    # Sort tasks by suitability score (highest first)
    task_evaluations.sort(key=lambda x: x[1], reverse=True)

    # Select best tasks while respecting energy constraints
    selected_tasks = []
    remaining_energy = available_energy

    for task_index, _, energy_cost in task_evaluations:
        if energy_cost <= remaining_energy:
            selected_tasks.append(task_index)
            remaining_energy -= energy_cost

            # Stop if we're running low on energy reserve
            if remaining_energy < min_energy_reserve:
                break

    # Introduce some randomness while maintaining general preference order
    if selected_tasks:
        # Randomly shuffle within groups of similar suitability
        group_size = max(1, len(selected_tasks) // 3)
        for i in range(0, len(selected_tasks), group_size):
            group = selected_tasks[i : i + group_size]
            global_random.shuffle(group)
            selected_tasks[i : i + group_size] = group

    return selected_tasks
