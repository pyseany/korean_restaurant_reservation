from modules.entities import EntityTracker
from modules.bow import BoW_encoder
from  modules.lstm_net import LSTM_net
from modules.embed import UtteranceEmbed
from modules.actions import ActionTracker
from modules.data_utils import Data
import joblib
import numpy as np
import sys


class Trainer():

    def __init__(self):

        et = EntityTracker()
        self.bow_enc = BoW_encoder()
        self.emb = UtteranceEmbed()
        at = ActionTracker(et)

        self.dataset, dialog_indices = Data(et, at).trainset
        
        train_indices = joblib.load('data/train_test_list/train_indices_759')
        test_indices = joblib.load('data/train_test_list/test_indices_759_949')
        
        self.dialog_indices_tr = train_indices
        self.dialog_indices_dev = test_indices

        obs_size = self.emb.dim + self.bow_enc.vocab_size + et.num_features
        self.action_templates = at.get_action_templates()
        action_size = at.action_size
        nb_hidden = 128

        self.net = LSTM_net(obs_size=obs_size,
                       action_size=action_size,
                       nb_hidden=nb_hidden)

    def train(self):
        print('\n:: training started\n')
        epochs = 20
        for j in range(epochs):
            # iterate through dialogs
            num_tr_examples = len(self.dialog_indices_tr)
            loss = 0.
            for i,dialog_idx in enumerate(self.dialog_indices_tr):
                # get start and end index
                start, end = dialog_idx['start'], dialog_idx['end']
                # train on dialogue
                loss += self.dialog_train(self.dataset[start:end])
                # print #iteration
                sys.stdout.write('\r{}.[{}/{}]'.format(j+1, i+1, num_tr_examples))

            print('\n\n:: {}.tr loss {}'.format(j+1, loss/num_tr_examples))
            # evaluate every epoch
            per_response_accuracy,  per_dialogue_accuracy= self.evaluate()
            print(':: {}.dev per_response_accuracy {}\n'.format(j+1, per_response_accuracy))
            print(':: {}.dev per_dialogue_accuracy {}\n'.format(j + 1, per_dialogue_accuracy))
        self.net.save()

    def dialog_train(self, dialog):
        # create entity tracker
        et = EntityTracker()
        # create action tracker
        at = ActionTracker(et)
        # reset network
        self.net.reset_state()

        loss = 0.
        # iterate through dialog
        for (u,r) in dialog:
            u_ent = et.extract_entities(u)
            u_ent_features = et.context_features()
            u_emb = self.emb.encode(u)
            u_bow = self.bow_enc.encode(u)
            # concat features
            features = np.concatenate((u_ent_features, u_emb, u_bow), axis=0)
            # get action mask
            action_mask = at.action_mask()
            # forward propagation
            #  train step
            loss += self.net.train_step(features, r, action_mask)
        return loss / len(dialog)

    def evaluate(self):
        # create entity tracker
        et = EntityTracker()
        # create action tracker
        at = ActionTracker(et)
        # reset network
        self.net.reset_state()

        dialog_accuracy = 0.
        correct_dialogue_count = 0
        for dialog_idx in self.dialog_indices_dev:
            
            start, end = dialog_idx['start'], dialog_idx['end']
            dialog = self.dataset[start:end]
            num_dev_examples = len(self.dialog_indices_dev)

            # create entity tracker
            et = EntityTracker()
            # create action tracker
            at = ActionTracker(et)
            # reset network
            self.net.reset_state()

            # iterate through dialog
            correct_examples = 0
            for (u,r) in dialog:
                # encode utterance
                u_ent = et.extract_entities(u)
                u_ent_features = et.context_features()
                u_emb = self.emb.encode(u)
                u_bow = self.bow_enc.encode(u)
                # concat features
                features = np.concatenate((u_ent_features, u_emb, u_bow), axis=0)
                # get action mask
                action_mask = at.action_mask()
                # forward propagation
                #  train step
                prediction = self.net.forward(features, action_mask)
                correct_examples += int(prediction == r)
                
            if correct_examples == len(dialog):
                correct_dialogue_count += 1
            # get dialog accuracy
            dialog_accuracy += correct_examples/ len(dialog)
        per_response_accuracy = dialog_accuracy / num_dev_examples
        per_dialogue_accuracy = correct_dialogue_count / num_dev_examples
        return per_response_accuracy, per_dialogue_accuracy



if __name__ == '__main__':
    # setup trainer
    trainer = Trainer()
    # start training
    trainer.train()
