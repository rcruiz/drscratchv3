class DuplicateScripts:
    """
    Plugin that analyzes a Scratch project to find duplicate scripts,
    which are repeated programs into a project.
    """

    def __init__(self):
        self.total_duplicate = 0
        self.blocks_dicc = {}  #assign a dict blocks_value
        self.total_blocks = []  #add a dict
        self.list_duplicate = []

    def analyze(self, json_project):
        """"
        Only takes into account scripts with more than 5 blocks.

        :param json_project: JSON of Scratch project. Its data are parsed as a dictionary.
        :return:
        """

        scripts_set = set()

        for key, value in json_project.iteritems():
            if key == "targets":
                for dicc in value:
                    for dicc_key, dicc_value in dicc.iteritems():
                        if dicc_key == "blocks":
                            for blocks, blocks_value in dicc_value.iteritems():
                                if type(blocks_value) is dict:
                                    self.blocks_dicc[blocks] = blocks_value
                                    self.total_blocks.append(blocks_value)
        print(blocks_value, "tttrtrtrtrtrt")
        for key_block in self.blocks_dicc:
            block = self.blocks_dicc[key_block]
            if block["topLevel"] == True:
                block_list = []
                block_list.append(block["opcode"])
                next = block["next"]
                aux_next = None
                self.search_next(next, block_list, key_block, aux_next)

                blocks_tuple = tuple(block_list)

                if blocks_tuple in scripts_set:
                    if len(block_list) > 5:
                        if not block_list in self.list_duplicate:
                            self.total_duplicate += 1
                            self.list_duplicate.append(block_list)
                else:
                    scripts_set.add(blocks_tuple)

    def search_next(self, next, block_list, key_block, aux_next):
        if next == None:
            try:
                # Maybe is a control_forever block
                next = self.blocks_dicc[key_block]["inputs"]["SUBSTACK"][1]
                if next == None:
                    return
            except:
                if aux_next != None:      #Check if there is a aux_next saved
                    next = aux_next
                    aux_next = None
                else:
                    next = None
                    return
        else:
            # Maybe is a loop block
            if "SUBSTACK" in self.blocks_dicc[key_block]["inputs"]:
                loop_block = self.blocks_dicc[key_block]["inputs"]["SUBSTACK"][1]
                #Check if is a loop block but EMPTY
                if loop_block != None:
                    aux_next = next          #Save the real next until the end of the loop
                    next = loop_block

        block = self.blocks_dicc[next]
        block_list.append(block["opcode"])
        key_block = next
        next = block["next"]
        self.search_next(next, block_list, key_block, aux_next)

    def finalize(self):
        """
        Output the duplicate scripts detected.
        :return:
        """

        result = ("%d duplicate scripts found" % self.total_duplicate)
        result += "\n"
        for duplicate in self.list_duplicate:
            result += str(duplicate)
            result += "\n"
        print result
        return result


def main(json_project):
    """The entrypoint for the 'duplicateScripts' extension"""

    duplicate = DuplicateScripts()
    duplicate.analyze(json_project)
    return duplicate.finalize()


