import pickle

#helper function to unsplit args
#argsList: list of args (first arg may not be what we need)
#starting_index: first word to start concatenating from
def concatenateArgs(argsList, starting_index, insert = ' '):
    concatArgs = argsList[starting_index]
    for i in range(starting_index + 1, len(argsList)):
        concatArgs = concatArgs + insert + argsList[i]
    return concatArgs


# def importpkl(**args):
#     exit()

# def exportpkl(**args):
#     args[0] = dir
#     args[1] = name
#     args[2] = 0
#     with open(dir+'/'+name+'.pickle', 'wb') as f:
#         pickle.dump([self.token, self.refresh_token], f)