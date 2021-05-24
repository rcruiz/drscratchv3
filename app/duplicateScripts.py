class DuplicateScripts:
    """
    Plugin that analyzes a Scratch project to find duplicate scripts,
    which are repeated programs into a project. When we instantiate
    an object of this class, we can analyze how many times the code
    of specific Scratch project use duplicated scripts,in the same
    sprite or in a different one.
    """

    def __init__(self):
        self.total_duplicate = 0
        self.blocks_dicc = {}  #assign a dict blocks_value
        self.total_blocks = []  #add a dict
        self.list_duplicate = []

    def analyze(self, json_project):
        """"
        This method search in a JSON data deserialized of a Scratch
        project, if there is duplicate code. Checks if the same stream
        of blocks are repeated elsewhere in the program. Only takes
        into account duplicated scripts with more than 5 blocks. Output
        that contains this duplicated blocks goes to self.list_duplicate.
        Number of duplicate scripts goes to self.total_duplicate.

        :param json_project: JSON of Scratch project. Its data are parsed
            as a dictionary.
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
        """
        The recursive method looks for the code that follows the
        duplicate code. Continue with the rest of the code, the next
        blocks after the duplicate code. It even checks the inner
        loops, if they exist.

        :param next: string with the value of dict of blocks store to
            search the next code.
        :param block_list: List with the values of block of code to
            search.
        :param key_block: key of self.blocks_dicc to search the next
            or a loop block.
        :param aux_next: none or block saved.
        """
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
                    aux_next = next  # Save the real next until the end of the loop
                    next = loop_block

        block = self.blocks_dicc[next]
        block_list.append(block["opcode"])
        key_block = next
        next = block["next"]
        self.search_next(next, block_list, key_block, aux_next)

    def finalize(self):
        """
        Return the duplicate scripts detected in the Scratch project.
        Take the value of attribute self.total_duplicate and retrieve the
        duplicated sets of blocks of the attribute self.list_duplicate.

        :return result: String with number and list of duplicated code.
        """
        result = ("%d duplicate scripts found" % self.total_duplicate)
        result += "\n"
        for duplicate in self.list_duplicate:
            result += str(duplicate)
            result += "\n"
        return result


def main(json_project):
    """The entrypoint for the 'duplicateScripts' extension.

    Creates a new instance of the class and assigns to object duplicate
    their attributes and methods. When method finalize is invoked, the object
    return total and list of duplicated scripts.

    :param json_project: Dictionary with a JSON data deserialized.
    :return result of duplicate code.
    """
    duplicate = DuplicateScripts()
    duplicate.analyze(json_project)
    return duplicate.finalize()
