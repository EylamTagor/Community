from global_random import global_random
from typing import List
from collections import defaultdict
from tqdm import tqdm
import logging
from time import process_time
import argparse
import importlib.util
import sys
import functools
import io
# group 2 needs this package, and if only imported in our file, the simulator will catch the exception and play default
# therefore, we import it here to ensure a ModuleNotFound crash, so that the error won't go unnoticed
import scipy as _ 
import csv
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
#import matplotlib.pyplot as plt
#from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
#from matplotlib.figure import Figure
import numpy as np
import os
from teams.team_0.distributions_easy import ability_distribution as default_ability_distribution
from teams.team_0.distributions_easy import task_difficulty_distribution as default_task_difficulty_distribution
global_task_generation_id = 0
time_prefI = 0
num_calls_prefI = 0
time_prefII = 0
num_calls_prefII = 0



class Member:
    def __init__(self, group: int, abilities: List[int], id: int):
        self._abilities = abilities
        self._energy = 10
        self._id = id
        self._group = group
        self._incapacitated = False

    @property
    def abilities(self):
        return self._abilities.copy()  # Return a copy to prevent direct modification

    @property
    def energy(self):
        return self._energy

    @property
    def id(self):
        return self._id

    @property
    def group(self):
        return self._group

    @property
    def incapacitated(self):
        return self._incapacitated

    def _modify_energy(self, amount):
        self._energy = min(10, self._energy + amount)
        if self._energy <= -10:
            self._incapacitated = True

    def _set_incapacitated(self, value: bool):
        self._incapacitated = value


class MemberActions:
    @staticmethod
    def rest(member: Member):
        if member.energy >= 0:
            member._modify_energy(1)
        elif member.energy < 0 and member.energy > -10:
            member._modify_energy(0.5)
        else:
            member._set_incapacitated(True)

    @staticmethod
    def perform_task(member: Member, task: 'Task', partner: 'Member' = None):
        energy_cost = 0
        for i in range(len(member.abilities)):
            if partner:
                skill = max(member.abilities[i], partner.abilities[i])
            else:
                skill = member.abilities[i]

            if task[i] > skill:
                energy_cost += task[i] - skill

        if partner:
            energy_cost /= 2

        member._modify_energy(-energy_cost)
        if member.energy <= -10:
            member._set_incapacitated(True)

        return energy_cost

class Community:
    def __init__(self, num_abilities: int, num_players: int, player_distribution, members):
        self.num_abilities = num_abilities
        self.members = members
        self.completed_tasks = 0
        self.tasks = []

class CommunityActions:
    @staticmethod
    def generate_tasks(community: Community, task_distribution):
        num_tasks = 2 * len(community.members)
        global global_task_generation_id
        # community.tasks = []
        for _ in range(num_tasks):
            # print(global_task_generation_id)
            try:
                task_distri = task_distribution(community.num_abilities, seed_task_difficulty, global_task_generation_id, global_random)
            except Exception as e:
                print(e)
                print(f"Unable to use given task distribution function. Using the default task distribution function.")
                task_distri = default_task_difficulty_distribution(community.num_abilities, seed_task_difficulty, global_task_generation_id, global_random)
            global_task_generation_id += 1
            assert min(task_distri) >= 0 and max(task_distri) <= 10, "Tasks difficulties should be in the range [0, 10]"
            assert len(task_distri) == community.num_abilities, f"Length of task distri ({len(task_distri.difficulties)}) does not match num_abilities ({community.num_abilities})"
            community.tasks.append(task_distri)
        community.tasks.sort(key=lambda x: sum(x), reverse=True)

    @staticmethod
    def simulate_turn(community: Community, task_distribution, available_players):
        if len(community.tasks) == 0:
            CommunityActions.generate_tasks(community, task_distribution)

        # Phase 1: Partnerships
        available_players = sorted(available_players, key=lambda x: x.id)
        partnerships = CommunityActions.form_partnerships(community, available_players)
        # print("Partnerships")
        for task_id in partnerships:
            player1ID = partnerships[task_id][0]
            player2ID = partnerships[task_id][1]
            # print(player1ID, player2ID)
            player1 = next(member for member in community.members if member.id == player1ID)
            player2 = next(member for member in community.members if member.id == player2ID)
            task = community.tasks[task_id]
            MemberActions.perform_task(player1, task, player2)
            MemberActions.perform_task(player2, task, player1)
            community.tasks[task_id] = []
            available_players.remove(player1)
            available_players.remove(player2)
            # print(player1.id, player2.id, task, sum(task), player1.abilities, player2.abilities, player1.energy, player2.energy)
            community.completed_tasks += 1

        while [] in community.tasks:
            community.tasks.remove([])

        # del partnerships
        # Phase 2: Individual tasks
        # available_players = sorted(available_players, key=lambda x: x.id)
        individual_tasks, available_players = CommunityActions.assign_individual_tasks(community, available_players)
        # print("Individual tasks")
        for task, player in individual_tasks:
            MemberActions.perform_task(player, task)
            # print(player.id, task, sum(task), player.abilities, player.energy)
            community.tasks.remove(list(task))
            community.completed_tasks += 1

        # del individual_tasks
        # Rest remaining players
        for player in available_players:
            if not player.incapacitated and player.energy < 10:
                MemberActions.rest(player)
        del available_players
        return partnerships, individual_tasks

    @staticmethod
    def form_partnerships(community: Community, available_players):
        all_partnerships = defaultdict(list)
        bids = {}
        available_players_id = [p.id for p in available_players]
        # Collect preferences for all available players
        for player in available_players:
            pref = []
            global time_prefI
            global num_calls_prefI
            try:
                t1_start = process_time()
                pref = getPairPreferencesPhaseI(player, community)
                num_calls_prefI += 1
                t1_stop = process_time()
                time_prefI += t1_stop - t1_start
            # except Exception:
            except Exception as e:
                print(e)
                num_calls_prefI += 1
                print(f"Error getting partnership preferences for player {player.id} from group {player.group}. Assuming no preferences.")
            if pref is not None:
                bids[player.id] = pref
        # Process preferences to find valid pairs
        for player_id in available_players_id:
            if player_id in bids:
                for task_id, partner_id in bids[player_id]:
                    assert task_id < len(community.tasks), "Index should be within range while assigning partnership tasks"
                    # task = community.tasks[task_id]
                    # assert task in community.tasks, "The preferred task is not a community task, select valid tasks"
                    if partner_id == player_id:
                        continue
                    if partner_id in bids and [task_id, player_id] in bids[partner_id]:
                        pair = tuple(sorted([player_id, partner_id]))
                        if pair not in all_partnerships[task_id]:
                            all_partnerships[task_id].append(pair)

        # Randomly select one partnership per task and maximize overall partnerships
        final_partnerships = {}
        used_ids = set()

        # Sort tasks by number of partnerships (descending) to maximize overall partnerships
        sorted_tasks = sorted(all_partnerships.keys(), key=lambda t: sum(community.tasks[t]), reverse=True)

        for task_id in sorted_tasks:
            partnerships = all_partnerships[task_id]
            partnerships.sort()
            global_random.shuffle(partnerships)  # Randomize partnerships for this task
            for partnership in partnerships:
                if all(id not in used_ids for id in partnership):
                    final_partnerships[task_id] = list(partnership)
                    used_ids.update(partnership)
                    break  # Move to next task after finding a valid partnership
        # print(final_partnerships)
        return final_partnerships

    @staticmethod
    def assign_individual_tasks(community: Community, available_players):
        assignments = defaultdict(list)
        for player in available_players:
            tasksVolunteered = []
            global time_prefII
            global num_calls_prefII
            try:
                t1_start = process_time()
                tasksVolunteered = getPairPreferencesPhaseII(player, community)
                t1_stop = process_time()
                num_calls_prefII += 1
                time_prefII += t1_stop - t1_start
            except Exception as e:
                print(e)
                print(f"Error getting individual preferences for player {player.id} from group {player.group}. Assuming no preferences.")
                num_calls_prefII += 1
            # if tasksVolunteered:
            # print(player.id, tasksVolunteered)
            if tasksVolunteered is not None:
                for tasks_id in tasksVolunteered:
                    assert tasks_id < len(community.tasks), "Index should be within range while assigning individual tasks"
                    # tasks = community.tasks[tasks_id]
                    # assert tasks in community.tasks, "The preferred task is not a community task, select valid tasks"
                    assignments[tasks_id].append(player)
        sorted_tasks = sorted(assignments.keys(), key=lambda t: sum(community.tasks[t]), reverse=True)
        final_assignments = []
        for task_id in sorted_tasks:
            if not available_players:
                break
            player = global_random.choice(assignments[task_id])
            while (player not in available_players and len(assignments[task_id]) > 1):
                assignments[task_id].remove(player)
                player = global_random.choice(assignments[task_id])
            if player in available_players:
                available_players.remove(player)
                final_assignments.append((community.tasks[task_id], player))
        return [final_assignments, available_players]


def getPairPreferencesPhaseI(player, community):
    group = player.group
    func = import_class_from_file(f"teams/team_{group}", "preferences", "phaseIpreferences")
    return func(player, community, global_random)

def getPairPreferencesPhaseII(player, community):
    group = player.group
    func = import_class_from_file(f"teams/team_{group}", "preferences", "phaseIIpreferences")
    return func(player, community, global_random)


def import_class_from_file(folder, file_name, class_name):
    file_path = f"{folder}/{file_name}.py"
    spec = importlib.util.spec_from_file_location(file_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[file_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)

def setup_logger(flag):
    logger = logging.getLogger(flag)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(f"{flag}_log.txt")
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger

def log_output(flag):
    logger = setup_logger(flag)
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            original_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                result = func(*args, **kwargs)
                output = sys.stdout.getvalue()
                if output:
                    logger.info(f"Function {func.__name__} output:\n{output}")
                return result
            finally:
                sys.stdout = original_stdout
        return wrapper
    return decorator

def create_logged_function(func, flag):
    return log_output(flag)(func)


def run_simulation(num_abilities: int, num_players: int, player_distribution, num_turns: int, ability_distribution, task_difficulty_distribution, output_file: str):
    members = []
    j = 0
    for group, count in player_distribution.items():
        for _ in range(count):
            try:
                distri = ability_distribution(num_abilities, seed_ability, j, global_random)
            except Exception as e:
                print(e)
                print("Unable to use the given ability distribution function. Using the default ability distribution function.")
                distri = default_ability_distribution(num_abilities, seed_ability, j, global_random)
            assert  min(distri) >= 0 and max(distri) <= 10, "Ability distribution should be between [0, 10]"
            assert len(distri) == num_abilities, f"Length of distri ({len(distri)}) does not match num_abilities ({num_abilities})"
            members.append(Member(group, distri, j))
            j += 1

    community = Community(num_abilities, num_players, player_distribution, members)
    print(output_file)
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Turn', 'Completed Tasks', 'Tasks/Turn'])

    for turn in tqdm(range(num_turns), file=sys.stdout):
        available_players = {p for p in community.members if not p.incapacitated}
        if len(available_players) == 0:
            print("No active players")
            break
        CommunityActions.simulate_turn(community, task_difficulty_distribution, available_players)
    
        if (turn + 1) % 100 == 0:
            with open(output_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([turn + 1, community.completed_tasks, community.completed_tasks/(turn + 1)])
                print(f"Turn: {turn + 1}: {community.completed_tasks}. Average tasks completed: {community.completed_tasks/(turn + 1)}")

    return community.completed_tasks


def create_gui(community, run_simulation_func, task_difficulty_distribution, num_turns):
    root = tk.Tk()
    root.title("Community Task Simulation")
    root.geometry("1400x900")
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Main Dashboard
    dashboard_frame = ttk.Frame(notebook)
    notebook.add(dashboard_frame, text="Dashboard")

    # Community Overview
    overview_frame = ttk.LabelFrame(dashboard_frame, text="Community Overview")
    overview_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    total_members_label = ttk.Label(overview_frame, text=f"Total Members: {len(community.members)}")
    total_members_label.pack()
    active_members_label = ttk.Label(overview_frame,
                                     text=f"Active Members: {sum(1 for m in community.members if not m.incapacitated)}")
    active_members_label.pack()

    # Ability Distribution Chart
    ability_dist_frame = ttk.Frame(notebook)
    notebook.add(ability_dist_frame, text="Ability Distribution")

    # Create a Figure and Axes for the histogram
    fig = Figure(figsize=(12, 6))
    ax = fig.add_subplot(111)

    # Get ability data
    abilities = np.array([m.abilities for m in community.members])
    num_players = len(community.members)
    num_abilities = community.num_abilities

    # Create the stacked bar plot
    bar_width = 0.8
    colors = plt.cm.get_cmap('tab10')(np.linspace(0, 1, num_abilities))
    abilities_map = ["Food", "Water", "Clothing", "Building", "Plants", "Animals", "Transport", "Medicine"]

    # Create a figure and axis
    fig, ax = plt.subplots()

    # Calculate the x positions for each group of bars
    x_positions = np.arange(num_players)

    for i in range(num_abilities):
        # Offset each bar's position by its index multiplied by the bar width
        ax.bar(x_positions + i * bar_width / num_abilities,
               abilities[:, i],
               width=bar_width / num_abilities,
               color=colors[i],
               label=abilities_map[i])

    # Set x-ticks to be in the middle of the grouped bars
    ax.set_xticks(x_positions + bar_width*(num_abilities + 1)/2 / (2 * num_abilities))
    ax.set_xticklabels([f'{j + 1}' for j in range(num_players)])

    # Add legend and labels
    ax.legend()
    ax.set_xlabel('Players')
    ax.set_ylabel('Abilities')
    ax.set_title('Abilities Distribution for each player')

    # plt.show()
    # Create a canvas for the plot
    canvas = FigureCanvasTkAgg(fig, master=ability_dist_frame)
    canvas.draw()

    # Add a scrollbar
    scrollbar = ttk.Scrollbar(ability_dist_frame, orient=tk.HORIZONTAL)
    scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Connect the scrollbar to the canvas
    def scroll(event):
        canvas.get_tk_widget().xview_scroll(-1 * (event.delta // 120), "units")

    canvas.get_tk_widget().bind("<MouseWheel>", scroll)
    canvas.get_tk_widget().configure(xscrollcommand=scrollbar.set)
    scrollbar.configure(command=canvas.get_tk_widget().xview)

    # Add navigation toolbar
    toolbar = NavigationToolbar2Tk(canvas, ability_dist_frame)
    toolbar.update()

    # Function to handle automatic zoom out
    def auto_zoom_out():
        ax.autoscale()
        ax.set_xlim(ax.get_xlim()[0] * 1.1, ax.get_xlim()[1] * 1.1)
        ax.set_ylim(ax.get_ylim()[0] * 1.1, ax.get_ylim()[1] * 1.1)
        canvas.draw()

    # Create a custom zoom out button
    zoom_out_button = ttk.Button(ability_dist_frame, text="Zoom Out", command=auto_zoom_out)
    zoom_out_button.pack(side=tk.TOP)

    # Pack the canvas
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    # Task Board
    task_frame = ttk.LabelFrame(dashboard_frame, text="Task Board")
    task_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    task_tree = ttk.Treeview(task_frame, columns=("Difficulty",), show="headings")
    task_tree.heading("Difficulty", text="Difficulty")
    task_tree.column("Difficulty", width=200)
    task_tree.pack(fill=tk.BOTH, expand=True)

    for task in community.tasks:
        formatted_task = ", ".join(f"{difficulty:2d}" for difficulty in task)
        task_tree.insert("", "end", values=(formatted_task,))

    # Performance Metrics
    metrics_frame = ttk.LabelFrame(dashboard_frame, text="Performance Metrics")
    metrics_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    completed_tasks_label = ttk.Label(metrics_frame, text=f"Completed Tasks: {community.completed_tasks}")
    completed_tasks_label.pack()

    # Task Completion Details
    task_completion_frame = ttk.LabelFrame(dashboard_frame, text="Task Completion Details")
    task_completion_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    task_completion_tree = ttk.Treeview(task_completion_frame, columns=("Type", "Members", "Task"), show="headings")
    task_completion_tree.heading("Type", text="Type")
    task_completion_tree.heading("Members", text="Members")
    task_completion_tree.heading("Task", text="Task")
    task_completion_tree.pack(fill=tk.BOTH, expand=True)

    # Member Management
    member_frame = ttk.Frame(notebook)
    notebook.add(member_frame, text="Member Management")

    member_tree = ttk.Treeview(member_frame, columns=("ID", "Group", "Energy", "Abilities", "Status"), show="headings")
    member_tree.heading("ID", text="ID")
    member_tree.heading("Group", text="Group")
    member_tree.heading("Energy", text="Energy")
    member_tree.heading("Abilities", text="Abilities")
    member_tree.column("Abilities", width=200)
    member_tree.heading("Status", text="Status")
    member_tree.pack(fill=tk.BOTH, expand=True)

    for member in community.members:
        status = "Incapacitated" if member.incapacitated else "Active"
        formatted_abilities = ", ".join(f"{ability:2d}" for ability in member.abilities)
        member_tree.insert("", "end", values=(member.id, member.group, f"{member.energy:.1f}", formatted_abilities, status))

    # Simulation Control
    control_frame = ttk.Frame(root)
    control_frame.pack(pady=10)

    current_turn = 0
    turn_label = ttk.Label(control_frame, text=f"Current Turn: {current_turn}")
    turn_label.pack(side=tk.LEFT, padx=5)

    def update_gui():
        nonlocal current_turn
        # Update task board
        task_tree.delete(*task_tree.get_children())
        # print(len(community.tasks))
        for task in community.tasks:
            formatted_task = ", ".join(f"{difficulty:2d}" for difficulty in task)
            task_tree.insert("", "end", values=(formatted_task,))

        # Update member tree
        member_tree.delete(*member_tree.get_children())
        for member in community.members:
            status = "Incapacitated" if member.incapacitated else "Active"
            if member.energy < 0 and member.energy> -10:
                status = "Tired"
            formatted_abilities = ", ".join(f"{ability:2d}" for ability in member.abilities)
            member_tree.insert("", "end", values=(member.id, member.group, f"{member.energy:.1f}", formatted_abilities, status))

        # Update metrics
        completed_tasks_label.config(text=f"Completed Tasks: {community.completed_tasks}")

        # Update community overview
        total_members_label.config(text=f"Total Members: {len(community.members)}")
        active_members_label.config(text=f"Active Members: {sum(1 for m in community.members if not m.incapacitated)}")

        # Update turn label
        turn_label.config(text=f"Current Turn: {current_turn}")

        # Redraw the canvas
        canvas.draw()

    def run_turn():
        nonlocal current_turn
        if current_turn < num_turns:
            # Clear previous turn's task completion details
            task_completion_tree.delete(*task_completion_tree.get_children())

            # Run the simulation turn and capture partnerships and individual tasks
            available_players = {p for p in community.members if not p.incapacitated}
            final_partnerships, individual_tasks = run_simulation_func(community, task_difficulty_distribution, available_players)

            # Update task completion details with partnerships
            for task, partners in final_partnerships.items():
                task_completion_tree.insert("", "end", values=(
                "Partnership", f"{partners[0]}, {partners[1]}", f"{task} (Sum: {sum(task)})"))

            # Update task completion details with individual tasks
            for task, player in individual_tasks:
                task_completion_tree.insert("", "end", values=("Individual", player.id, f"{task} (Sum: {sum(task)})"))

            current_turn += 1
            update_gui()

        if current_turn >= num_turns:
            messagebox.showinfo("Simulation Complete", f"Simulation completed after {num_turns} turns.")
            step_button.config(state="disabled")
            run_all_button.config(state="disabled")

    def run_entire_simulation():
        nonlocal current_turn
        while current_turn < num_turns:
            run_turn()
        messagebox.showinfo("Simulation Complete", f"Simulation completed after {num_turns} turns.")
        step_button.config(state="disabled")
        run_all_button.config(state="disabled")

    step_button = ttk.Button(task_frame, text="Step", command=run_turn)
    step_button.pack(side=tk.LEFT, padx=5)

    run_all_button = ttk.Button(task_frame, text="Run Entire Simulation", command=run_entire_simulation)
    run_all_button.pack(side=tk.LEFT, padx=5)

    def on_closing(root):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.quit()
            root.destroy()
            import sys
            sys.exit()

    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Game Configurations')
    parser.add_argument('--num_members', type=int, default=10, help='Total number of members in the community')
    parser.add_argument('--num_turns', type=int, default=100, help='Number of turns')
    parser.add_argument('--num_abilities', type=int, default=3, choices=range(3, 9),
                        help='Number of abilities (choice between 3 and 8)')
    parser.add_argument('--seed', type=int, default=42, help='Seed for entire simulation')
    parser.add_argument('--seed_ability', type=int, default=42, help='Seed for ability distribution randomness')
    parser.add_argument('--seed_task_difficulty', type=int, default=42, help='Seed for task difficulty randomness')
    parser.add_argument('--group_task_distribution', type=int, default=0, choices=range(0, 11), help='Task distribution of group selected')
    parser.add_argument('--task_distribution_difficulty', type=str, default='easy', choices=['easy', 'medium', 'hard'], help='Easy (e), medium (m) or hard difficulty')
    parser.add_argument('--group_abilities_distribution', type=int, default=0, choices=range(0, 11), help='Ability distribution of group selected')
    parser.add_argument('--abilities_distribution_difficulty', type=str, default='easy', choices=['easy', 'medium', 'hard'], help='Easy (e), medium (m) or hard difficulty')
    parser.add_argument('--log', action='store_true', help='Log the results to a txt in folder')
    parser.add_argument('--gui', action='store_true', help='Run the simulation with GUI')
    parser.add_argument('--output_file', type=str, help='Path to the output CSV file')
    for i in range(1, 11):
        parser.add_argument(f'--g{i}', type=int, default=0, help=f'Number of players in group {i}')

    args, _ = parser.parse_known_args()
    global_random.seed(args.seed)
    num_members = args.num_members
    num_turns = args.num_turns
    num_abilities = args.num_abilities
    ability_team = args.group_abilities_distribution
    task_difficulty_distribution_team = args.group_task_distribution
    seed_ability = args.seed_ability
    seed_task_difficulty = args.seed_task_difficulty

    group_players = sum(getattr(args, f'g{i}') for i in range(1, 11))
    g0_players = num_members - group_players

    if g0_players < 0:
        raise AssertionError(
            "The sum of member distribution provided among groups exceeds the total number of members given")
    elif g0_players == 0:
        print("All players have been distributed among groups g1 to g10 with the distribution provided")
    else:
        print(f"{g0_players} players have been assigned to the default group 0")

    player_distribution = {0: g0_players}
    for i in range(1, 11):
        if getattr(args, f'g{i}'):
            player_distribution[i] = getattr(args, f'g{i}')

    print("Player distribution:")
    for group, count in player_distribution.items():
        if count > 0:
            print(f"Group {group}: {count} players")

    file_name = "distributions"
    function_name_ability = "ability_distribution"
    function_name_task_difficulty = "task_difficulty_distribution"
    task_difficulty = args.task_distribution_difficulty

    try:
        ability_distribution = import_class_from_file(f'teams/team_{ability_team}', file_name + f'_{args.abilities_distribution_difficulty}', function_name_ability)
    except Exception as e:
        print(e)
        ability_distribution = import_class_from_file(f'teams/team_0', file_name + '_easy', function_name_ability)
        print(f"Import from team {ability_team} failed. Using default ability distribution")

    if args.log:
        ability_distribution = create_logged_function(ability_distribution,f"./log-results/team_{ability_team}_ability")

    try:
        task_difficulty_distribution = import_class_from_file(f'teams/team_{task_difficulty_distribution_team}', file_name + f'_{args.task_distribution_difficulty}', function_name_task_difficulty)

    except Exception as e:
        print(e)
        task_difficulty_distribution = import_class_from_file(f'teams/team_0', file_name + '_easy', function_name_task_difficulty)
        print(
            f"Import from team {task_difficulty_distribution_team} failed. Using default task difficulty distribution")
    if args.log:
        task_difficulty_distribution = create_logged_function(task_difficulty_distribution,f"./log-results/team_{task_difficulty_distribution_team}_taskdistribution")
    # total_tasks_completed = run_simulation(num_abilities, num_members, player_distribution, num_turns,
                                           # ability_distribution, task_difficulty_distribution)
    if args.gui:
        members = []
        j = 0
        for group, count in player_distribution.items():
            for _ in range(count):
                distri = ability_distribution(num_abilities, seed_ability, j, global_random)
                assert min(distri) >= 0 and max(distri) <= 10, "Ability distribution should be between [0, 10]"
                assert len(
                    distri) == num_abilities, f"Length of distri ({len(distri)}) does not match num_abilities ({num_abilities})"
                members.append(Member(group, distri, j))
                j += 1
        community = Community(num_abilities, num_members, player_distribution, members)
        CommunityActions.generate_tasks(community, task_difficulty_distribution)
        create_gui(community, CommunityActions.simulate_turn, task_difficulty_distribution, num_turns)
    else:
        total_tasks_completed = run_simulation(num_abilities, num_members, player_distribution, num_turns, ability_distribution, task_difficulty_distribution, args.output_file)
        
        print(f"Total tasks completed: {total_tasks_completed}")
        print(f"Average number of tasks per turn: {round(total_tasks_completed / num_turns, 2)}")
    print(f"Average time taken for giving phase I preferences: {round(time_prefI/num_calls_prefI, 2)} seconds")
    print(f"Average time taken for giving phase II preferences: {round(time_prefII / num_calls_prefII, 2)} seconds")
