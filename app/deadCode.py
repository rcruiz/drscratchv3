import logging

logger = logging.getLogger(__name__)


class DeadCode:
    """
    Search blocks of Scratch Project that never are executed or
    unreachable code.
    """

    def __init__(self):

        self.dead_code_instances = 0
        self.opcode_argument_reporter = "argument_reporter"
        self.event_variables = ["event_broadcastandwait", "event_whenflagclicked",
                                "event_whengreaterthan", "event_whenkeypressed",
                                "event_whenthisspriteclicked", "event_whenbackdropswitchesto",
                                "procedures_prototype", "procedures_definition"]

        self.loop_blocks = ["control_repeat", "control_forever", "control_if", "control_if_else",
                            "control_repeat_until"]

    def analyze(self, json_project):
        """
        Run and return the results from the DeadCode plugin.
        Search blocks match with event_variables or loop_blocks
        no initialized in class attributes. Check inputs of block.

        With an iterator over the (key, value) items of json_project,

        :param json_project: JSON of Scratch project.
        :return dict_sprites: dictionary with unreachable blocks.
        """

        dict_sprites = {}

        for key, value in json_project.iteritems():
            if key == "targets":
                for dicc in value:
                    sprite = dicc["name"]
                    blocks_list = []
                    for _, blocks_dicc in dicc["blocks"].iteritems():
                        if type(blocks_dicc) is dict:
                            event_variable = any(blocks_dicc["opcode"] == event for event in self.event_variables)
                            loop_block = any(blocks_dicc["opcode"] == loop for loop in self.loop_blocks)

                            if event_variable == False:

                                if not self.opcode_argument_reporter in blocks_dicc["opcode"]:

                                    if blocks_dicc["parent"] == None and blocks_dicc["next"] == None:
                                        blocks_list.append(str(blocks_dicc["opcode"]))

                                    # Check dead loop blocks
                                    if loop_block and blocks_dicc["opcode"] not in blocks_list:
                                        if not blocks_dicc["inputs"]:
                                            # Empty loop block, but inside of a block structure
                                            blocks_list.append(str(blocks_dicc["opcode"]))
                                        elif "SUBSTACK" not in blocks_dicc["inputs"]:
                                            blocks_list.append(str(blocks_dicc["opcode"]))
                                        else:
                                            # Could be normal loop block
                                            if blocks_dicc["inputs"]["SUBSTACK"][1] == None:
                                                blocks_list.append(str(blocks_dicc["opcode"]))

                    if blocks_list:
                        dict_sprites[sprite] = blocks_list
                        self.dead_code_instances += 1

        return dict_sprites

    def finalize(self, dicc_deadCode, filename):
        """
        Output the number of instances that contained dead code.

        :param dicc_deadCode: Dictionary with dead code blocks
        :param filename:
        :return result: String
        """

        result = ""
        result += filename
        if self.dead_code_instances > 0:
            result += "\n"
            result += str(dicc_deadCode)

        return result


def main(json_project, filename):
    """
    The entrypoint for the 'deadCode' extension
    """
    deadCode = DeadCode()
    dict_deadcode = deadCode.analyze(json_project)
    return deadCode.finalize(dict_deadcode, filename)
