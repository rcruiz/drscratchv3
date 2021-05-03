import json
from collections import Counter


class Mastery:
    """
    This class allows
    Plugin that infers the competence demonstrated by a developer on the
    following seven skills:abstraction and problem decomposition, logical
    thinking, algorithmic, notions of flow control, synchronization,
    parallelism, user interactivity and data representation. The evaluation
    of the competence level of each of these concepts follows the rules in
    https://dl.acm.org/doi/abs/10.1145/2818314.2818338
    """

    def __init__(self):
        self.mastery_dicc = {}		        #New dict to save punctuation
        self.total_blocks = []              #List with blocks
        self.blocks_dicc = Counter()		#Dict with blocks. keys are the words and values the count of occurrence.

    def process(self, json_project):
        """Start the analysis. ###
        Save the dictionary of utilized blocks to resolve the project,
        in the attribute self.total_blocks of type list. The counter
        add one to keep track of self.blocks_dicc values, when find
        the key opcode in dictionary stored in the list.

        :param json_project: JSON of project sb3.
        """

        for key, value in json_project.iteritems():
            if key == "targets":
                for dicc in value:
                    for dicc_key, dicc_value in dicc.iteritems():
                        if dicc_key == "blocks":
                            for blocks, blocks_value in dicc_value.iteritems():
                                if type(blocks_value) is dict:
                                    self.total_blocks.append(blocks_value)
  
        for block in self.total_blocks:
            for key, value in block.iteritems():
                if key == "opcode":
                    self.blocks_dicc[value] += 1

    def analyze(self):
        """
        Call methods with a specific CT skill to be analyzed.
        """
        self.logic()
        self.flow_control()
        self.synchronization()
        self.abstraction()
        self.data_representation()
        self.user_interactivity()
        self.parallelization()

    def finalize(self, filename):
        """Output the overall programming competence.###

        The skill to program is updated on string result. Result includes
        filename, attribute mastery_dicc and the obtained mastery points.

        :param filename: Project sb3.
        :return result: This string shows the total and average mastery of
        the evaluated project, including its proficiency level.
        """
        result = ""

        result += filename
        result += '\n'

        result += json.dumps(self.mastery_dicc)
        result += '\n'
   
        total = 0
        for i in self.mastery_dicc.items():
            total += i[1]
        result += ("Total mastery points: %d/21\n" % total)
   
        average =  float (total) / 7
        result += ("Average mastery points: %.2f/3\n" % average)

        if average > 2:
            result += "Overall programming competence: Proficiency"
        elif average > 1:
            result += "Overall programming competence: Developing"
        else:
            result += "Overall programming competence: Basic"

        return result

    def logic(self):
        """Assign the Logic skill result.

        This method gives the maximum score when logical operations have
        been used to resolve the Scratch project. The score decreases when
        if-else block or if block are utilized. Save the logic score into
        self.mastery_dicc['Logic'].

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['Logic'].
        """
        operations = {'operator_and', 'operator_or', 'operator_not'}
        score = 0
  
        for operation in operations:
            if self.blocks_dicc[operation]:
                score = 3
                self.mastery_dicc['Logic'] = score
                return
  
        if self.blocks_dicc['control_if_else']:
            score = 2
        elif self.blocks_dicc['control_if']:
            score = 1
  
        self.mastery_dicc['Logic'] = score

    def flow_control(self):
        """Assign the Flow Control skill result.

        Assess algorithmic notions of flow control. Value the use of
        blocks 'control repeat until' and that the exit condition is
        adequate (3 points). The values analyzed to evaluate this CT
        are collected in self.blocks_dicc. Save the flow_control score
        into self.mastery_dicc['FlowControl'].

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['FlowControl].
        """
        score = 0
  
        if self.blocks_dicc['control_repeat_until']:
            score = 3
        elif self.blocks_dicc['control_repeat'] or self.blocks_dicc['control_forever']:
            score = 2
        else:
            for block in self.total_blocks:
                for key, value in block.iteritems():
                    if key == "next" and value != None:
                        score = 1
                        break

        self.mastery_dicc['FlowControl'] = score

    def synchronization(self):
        """
        Assign a score (int variable) associated with the skill Syncronization,
        according the type of used blocks. ### Do not details. If not empty ###

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['Synchronization'].
        """
        score = 0
   
        if self.blocks_dicc['control_wait_until'] or self.blocks_dicc['event_whenbackdropswitchesto'] or self.blocks_dicc['event_broadcastandwait']:
            score = 3
        elif self.blocks_dicc['event_broadcast'] or self.blocks_dicc['event_whenbroadcastreceived'] or self.blocks_dicc['control_stop']:
            score = 2
        elif self.blocks_dicc['control_wait']:
            score = 1
  
        self.mastery_dicc['Synchronization'] = score

    def abstraction(self):
        """Assign the Abstraction skill result.

        Value the use of clones or abstraction of a single object,
        which are dynamically created and deleted, if the implementation
        requires them.

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['Abstraction'].
        """
        score = 0
        
        if self.blocks_dicc['control_start_as_clone']:
            score = 3
        elif self.blocks_dicc['procedures_definition']:
            score = 2
        else:
            count = 0
            for block in self.total_blocks:
                for key, value in block.iteritems():
                    if key == "parent" and value == None:
                        count += 1

            if count > 1:
                score = 1

        self.mastery_dicc['Abstraction'] = score

    def data_representation(self):
        """Assign the Data representation skill result.

        Based on the sets given in modifiers or lists, find if any
        match with the key in self.blocks_dicc. A integer variable
        score is assigned depending on the key found.

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['DataRepresentation'].
        """
        score = 0
  
        modifiers = {'motion_movesteps', 'motion_gotoxy', 'motion_glidesecstoxy', 'motion_setx', 'motion_sety',
                     'motion_changexby', 'motion_changeyby', 'motion_pointindirection', 'motion_pointtowards',
                     'motion_turnright', 'motion_turnleft', 'motion_goto',
                     'looks_changesizeby', 'looks_setsizeto', 'looks_switchcostumeto', 'looks_nextcostume',
                     'looks_changeeffectby', 'looks_seteffectto', 'looks_show', 'looks_hide', 'looks_switchbackdropto',
                     'looks_nextbackdrop'}

        lists = {'data_lengthoflist', 'data_showlist', 'data_insertatlist', 'data_deleteoflist', 'data_addtolist',
                 'data_replaceitemoflist', 'data_listcontainsitem', 'data_hidelist', 'data_itemoflist'}
        
        for item in lists:
            if self.blocks_dicc[item]:
                score = 3
                self.mastery_dicc['DataRepresentation'] = score
                return
  
        if self.blocks_dicc['data_changevariableby'] or self.blocks_dicc['data_setvariableto']:
            score = 2
        else:
            for modifier in modifiers:
                if self.blocks_dicc[modifier]:
                    score = 1

        self.mastery_dicc['DataRepresentation'] = score

    def user_interactivity(self):
        """
        Assign the User Interactivity skill result.

        No input parameters, no return value.
        Input comes from self.blocks_dicc.
        Output goes to self.mastery_dicc['UserInteractivity'].
        """
        score = 0
       
        proficiency = {'videoSensing_videoToggle', 'videoSensing_videoOn', 'videoSensing_whenMotionGreaterThan',
                       'videoSensing_setVideoTransparency', 'sensing_loudness'}
        
        developing = {'event_whenkeypressed', 'event_whenthisspriteclicked', 'sensing_mousedown', 'sensing_keypressed',
                 'sensing_askandwait', 'sensing_answer'}

        for item in proficiency:
            if self.blocks_dicc[item]:
                self.mastery_dicc['UserInteractivity'] = 3
                return

        for item in developing:
            if self.blocks_dicc[item]:
                self.mastery_dicc['UserInteractivity'] = 2
                return

        if self.blocks_dicc['motion_goto_menu']:
            if self.check_mouse() == 1:
                self.mastery_dicc['UserInteractivity'] = 2
                return
        if self.blocks_dicc['sensing_touchingobjectmenu']:
            if self.check_mouse() == 1:
                self.mastery_dicc['UserInteractivity'] = 2
                return
        if self.blocks_dicc['event_whenflagclicked']:
            score = 1
    
        self.mastery_dicc['UserInteractivity'] = score

    def check_mouse(self):
        """
        Check whether there is a block 'go to mouse' or 'touching mouse-pointer?' ToDo

        return
        """
        for block in self.total_blocks:
            for key, value in block.iteritems():
                if key == 'fields':
                    for mouse_key, mouse_val in value.iteritems():
                        if (mouse_key == 'TO' or mouse_key =='TOUCHINGOBJECTMENU') and mouse_val[0] == '_mouse_':
                            return 1
        return 0


    def parallelization (self):
        """
        Assign the parallelization skill result

        """
       
        score = 0
        keys = []
        messages = []
        backdrops = []
        multimedia = []
        dict_parall = {}
 
        dict_parall = self.parallelization_dict()

        if self.blocks_dicc['event_whenbroadcastreceived'] > 1:            # 2 Scripts start on the same received message
            if dict_parall['BROADCAST_OPTION']:
                var_list = set(dict_parall['BROADCAST_OPTION'])
                for var in var_list:
                    if dict_parall['BROADCAST_OPTION'].count(var) > 1:
                        score = 3
                        self.mastery_dicc['Parallelization'] = score
                        return

        if self.blocks_dicc['event_whenbackdropswitchesto'] > 1:           # 2 Scripts start on the same backdrop change
            if dict_parall['BACKDROP']:
                backdrop_list = set(dict_parall['BACKDROP'])
                for var in backdrop_list:
                    if dict_parall['BACKDROP'].count(var) > 1:
                        score = 3
                        self.mastery_dicc['Parallelization'] = score
                        return

        if self.blocks_dicc['event_whengreaterthan'] > 1:                  # 2 Scripts start on the same multimedia (audio, timer) event
            if dict_parall['WHENGREATERTHANMENU']:
                var_list = set(dict_parall['WHENGREATERTHANMENU'])
                for var in var_list:
                    if dict_parall['WHENGREATERTHANMENU'].count(var) > 1:
                        score = 3
                        self.mastery_dicc['Parallelization'] = score
                        return

        if self.blocks_dicc['videoSensing_whenMotionGreaterThan'] > 1:     # 2 Scripts start on the same multimedia (video) event
            score = 3
            self.mastery_dicc['Parallelization'] = score
            return
 
        if self.blocks_dicc['event_whenkeypressed'] > 1:                   # 2 Scripts start on the same key pressed
            if dict_parall['KEY_OPTION']:
                var_list = set(dict_parall['KEY_OPTION'])
                for var in var_list:
                    if dict_parall['KEY_OPTION'].count(var) > 1:
                        score = 2

        if self.blocks_dicc['event_whenthisspriteclicked'] > 1:           # Sprite with 2 scripts on clicked
            score = 2
  
        if self.blocks_dicc['event_whenflagclicked'] > 1 and score == 0:  # 2 scripts on green flag
            score = 1

        self.mastery_dicc['Parallelization'] = score

    def parallelization_dict(self):
        """
        Search within the dictionary by the fields key those blocks with
        any of the pressed values specified above. Add the blocks with
        this requirement to the list saved in the dictionary.

        :return dicc: Dictionary containing the blocks with value pressed of parallelization.
        """

        dicc = {}

        print(self.total_blocks)

        for block in self.total_blocks:
            for key, value in block.iteritems():
                if key == 'fields':
                    for key_pressed, val_pressed in value.iteritems():
                        if key_pressed in dicc:
                            dicc[key_pressed].append(val_pressed[0])
                        else:
                            dicc[key_pressed] = val_pressed


        print(dicc)
        return dicc


def main(json_project, filename):
    """
    The entrypoint for the `Mastery` extension
    """
    mastery = Mastery()
    mastery.process(json_project)
    mastery.analyze()
    return mastery.finalize(filename)





