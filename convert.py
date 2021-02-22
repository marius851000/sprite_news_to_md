from git import Repo
import json

CHANGE_DISPLAY_URL = "https://github.com/PMDCollab/SpriteCollab/commit/"

class SpriteCollabChangeExplorer:
    def __init__(self, repo_path):
        self.repo = Repo(repo_path)
    
    def get_change(self, revision):
        self.repo.head.reference = self.repo.commit(revision)
        previous_commit = None
        next_one_is_good = False
        for commit in self.repo.iter_commits():
            if commit.hexsha == revision:
                next_one_is_good = True
                revision = commit
            elif next_one_is_good:
                previous_commit = commit
                break
        if previous_commit == None:
            raise BaseException("the commit wasn't found")
        self.repo.git.checkout(previous_commit)
        diff = self.repo.index.diff(revision)

        data = {
            "pokemon": {}  
        }

        def check_pokemon_exist(id):
            if id not in data["pokemon"]:
                data["pokemon"][id] = {
                    "portrait": {
                        "added": [],
                        "modified": [],
                        "removed": []
                    },
                    "sprite": {
                        "added": [],
                        "modified": [],
                        "removed": [],
                    }
                }
        
        for change in diff:
            first_part = change.b_path.split("/")[0]
            if first_part == "portrait":
                changed_category = "portrait"
            elif first_part == "tracker.json":
                changed_category = "tracker"
            elif first_part == "credit_names.txt":
                changed_category = "credit"
            elif first_part == "sprite":
                changed_category = "sprite"
            else:
                raise BaseException("unknown category", first_part)
            
            if not change.b_path.endswith(".png"):
                continue
            
            if first_part in [ "portrait", "sprite" ]:
                changed_pokemon_id = change.b_path[len(change.b_path.split("/")[0])+1:-len(change.b_path.split("/")[-1])-1]
                check_pokemon_exist(changed_pokemon_id)
                changed_file_name = change.b_path.split("/")[-1].split(".")[0].lower()

            if change.change_type == "A": # file added
                if changed_category == "portrait":
                    # new portrait added
                    data["pokemon"][changed_pokemon_id]["portrait"]["added"].append(changed_file_name)
                elif changed_category == "sprite":
                    data["pokemon"][changed_pokemon_id]["sprite"]["added"].append(changed_file_name)
                elif changed_category in ["tracker", "credit"]:
                    pass
                else:
                    raise BaseException()
            elif change.change_type == "M": # modified
                if changed_category in ["tracker", "credit"]:
                    pass
                elif changed_category == "portrait":
                    # portrait modified
                    data["pokemon"][changed_pokemon_id]["portrait"]["modified"].append(changed_file_name)
                elif changed_category == "sprite":
                    data["pokemon"][changed_pokemon_id]["sprite"]["added"].append(changed_file_name)
                else:
                    raise BaseException()
            elif change.change_type == "D": # del
                if changed_category == "portrait":
                    data["pokemon"][changed_pokemon_id]["portrait"]["removed"].append(changed_file_name)
                elif changed_category == "sprite":
                    data["pokemon"][changed_pokemon_id]["portrait"]["removed"].append(changed_file_name)
                else:
                    raise BaseException()
            else:
                raise BaseException()
        
        for changed_pokemon_id in data["pokemon"]:
            for sprite_modified in data["pokemon"][changed_pokemon_id]["sprite"]["modified"]:
                if sprite_modified in data["pokemon"][changed_pokemon_id]["sprite"]["added"]:
                    del data["pokemon"][changed_pokemon_id]["sprite"]["added"][sprite_modified]

        tracker_data = revision.tree["tracker.json"].data_stream.read()
        tracker = json.loads(tracker_data)
        
        credit_data = {}
        credit_file = revision.tree["credit_names.txt"].data_stream.read().decode("utf-8")
        
        for line in credit_file.split("\n")[1:]:
            if line == "":
                continue
            line_splited = line.split("\t")
            name = line_splited[0]
            if name == "":
                name = None
            identifier = line_splited[1]
            site = line_splited[2]
            if site == "":
                site = None
            
            this_credit = {
                "name": name,
                "id": identifier,
                "site": site
            }
            credit_data[identifier] = this_credit

        def credit(identifier):
            if identifier == '':
                return None
            return credit_data[identifier]

        for pokemon_id in data["pokemon"]:
            split_slash = pokemon_id.split("/")
            main_group = split_slash[0]
            other_group = split_slash[1:]

            pokemon_data = tracker[main_group]
            pokemon_name = pokemon_data["name"]
            for subgroup_id in other_group:
                pokemon_data = pokemon_data["subgroups"][subgroup_id]
                if pokemon_data["name"] != "":
                    pokemon_name += " " + pokemon_data["name"]
            data["pokemon"][pokemon_id]["name"] = pokemon_name
            data["pokemon"][pokemon_id]["portrait_credit"] = credit(pokemon_data["portrait_credit"])
            data["pokemon"][pokemon_id]["sprite_credit"] = credit(pokemon_data["sprite_credit"])

        return data
    
    def generate_md_for_change(self, hash, tabulation):
        def format_action(changes, action, changed_singular, changed_plurial, into):
            change_number = len(changes)
            if change_number > 0:
                if change_number > 6:
                    into.append("{} {} {}".format(action, change_number, changed_plurial))
                else:
                    if change_number == 1:
                        into.append("{} the {} {}".format(action, changes[0], changed_singular))
                    else:
                        into.append("{} the {} {}".format(action, format_list_human(changes), changed_plurial))
        
        def format_list_human(actions):
            if len(actions) == 0:
                return ""
            elif len(actions) == 1:
                return actions[0]
            else:
                return ", ".join(actions[0:-1]) + " and "+actions[-1]
        
        def format_change(actions, credit, pokemon_name):
            credit_text = ""
            if credit["name"] != None:
                credit_text += credit["name"]
            else:
                credit_text += "the user with the discord id {}".format(credit["id"])
            
            if credit["site"] != None:
                #TODO: escape the content
                credit_text = "[{}]({})".format(credit_text, credit["site"])
            
            return tabulation + " " + credit_text + " [" + format_list_human(actions) + " for " + pokemon_name + "]("+CHANGE_DISPLAY_URL+hash+")." 

        data = self.get_change(hash)
        result = ""
        for pokemon_id in data["pokemon"]:
            pokemon = data["pokemon"][pokemon_id]
            pokemon_name = pokemon["name"]

            portrait_actions = []
            format_action(pokemon["portrait"]["added"], "added", "portrait", "portraits", portrait_actions)
            format_action(pokemon["portrait"]["removed"], "deleted", "portrait", "portraits", portrait_actions)
            format_action(pokemon["portrait"]["modified"], "changed", "portrait", "portraits", portrait_actions)

            if len(portrait_actions) > 0:
                result += format_change(portrait_actions, pokemon["portrait_credit"], pokemon_name) + "\n"


            sprite_actions = []
            format_action(pokemon["sprite"]["added"], "added", "sprite", "sprites", sprite_actions)
            format_action(pokemon["sprite"]["removed"], "deleted", "sprite", "sprites", sprite_actions)
            format_action(pokemon["sprite"]["modified"], "changed", "sprite", "sprites", sprite_actions)

            if len(sprite_actions) > 0:
                result += format_change(sprite_actions, pokemon["sprite_credit"], pokemon_name) + "\n"
            
        return result

def generate_range(explorer, start, end, tabulation):
    commits = []
    for commit in explorer.repo.iter_commits(end):
        commits.append(commit.hexsha)
        if commit.hexsha == start:
            break
    
    result = ""
    for commit in commits:
        result += tool.generate_md_for_change(commit, tabulation)
    return result

    

tool = SpriteCollabChangeExplorer("/home/marius/SpriteCollab/")
r = generate_range(tool, "a90126103d02b4df16a73c7da738649f7bbfebf9", "865b909c8b3038dd3778e561f1733a808bf04f06", "-")
print(r)
#print(tool.generate_md_for_change("a90126103d02b4df16a73c7da738649f7bbfebf9", "--"))
