'''
Created on June 04, 2017

@author: v-lianji
'''

import tensorflow as tf
import math
from time import clock
import numpy as np
import os
import pickle

from sklearn import metrics
from datetime import datetime, date


# return iterator of labels and features with 'batch size' and offset = text_dim
def load_data_from_file_batching(file, textfile, batch_size, text_dim):
    labels = []
    features = []
    cnt = 0

    with open(file, 'r') as rd, open(textfile, 'r') as textd:
        line_cnt = 0
        while True:
            cur_feature_list = []
            # read text vector
            line = textd.readline()
            if not line:
                break
            line = line.strip('\n')
            vect = line.split(' ')
            for idx in range(len(vect) - 1):  # remove last space
                if not vect[idx]:
                    print('vector read error&' + str(vect[idx]) + '&' + str(idx) + '&' + str(vect))
                    continue
                cur_feature_list.append([idx, float(vect[idx])])

            line = rd.readline()
            if not line:
                break
            line = line.strip('\n')
            cnt += 1
            label = float(line[0:1])
            if label > 1:
                label = 1
            feature_line = line[2:]
            words = feature_line.split(' ')
            for word in words:
                if not word:
                    continue
                tokens = word.split(':')
                cur_feature_list.append([text_dim+int(tokens[0]), float(tokens[1])])

            line_cnt = line_cnt + 1
            if line_cnt == 10:
                print(cur_feature_list)
            features.append(cur_feature_list)
            labels.append(label)
            if cnt == batch_size:
                yield labels, features
                labels = []
                features = []
                cnt = 0
    if cnt > 0:
        yield labels, features


# features: [[idx1,val], [idx2,val], ...]
# dim for original, cont_dim for continuous, word_dim for text
def prepare_data_4_sp(labels, features, dim, cont_dim, text_dim):
    instance_cnt = len(labels)

    indices = []    # feature indexes of each instance
    values = []     # feature values of each instance
    values_2 = []   # square of value of each instance
    cont_values = []
    text_values = []
    shape = [instance_cnt, dim]
    cont_shape = [instance_cnt, cont_dim]
    text_shape = [instance_cnt, text_dim]
    feature_indices = []

    for i in range(instance_cnt):
        m = len(features[i])
        cnt = 0
        for j in range(m):
            idx = features[i][j][0]
            if idx < text_dim:
                text_values.append(features[i][j][1])
            else:
                indices.append([i, idx - text_dim])
                values.append(features[i][j][1])
                values_2.append(features[i][j][1] * features[i][j][1])
                feature_indices.append(idx - text_dim)
                if text_dim + 19 <= idx <= text_dim + 28:
                    cont_values.append(features[i][j][1])
                    cnt += 1
        if cnt != 10:
            print('instance: ', i, cnt)

    res = {}
    res['indices'] = np.asarray(indices, dtype=np.int64)
    res['values'] = np.asarray(values, dtype=np.float32)
    res['values2'] = np.asarray(values_2, dtype=np.float32)
    res['cont_values'] = np.asarray(cont_values, dtype=np.float32)
    res['shape'] = np.asarray(shape, dtype=np.int64)
    res['cont_shape'] = np.asarray(cont_shape, dtype=np.int64)
    res['labels'] = np.asarray([[label] for label in labels], dtype=np.float32)
    res['feature_indices'] = np.asarray(feature_indices, dtype=np.int64)
    res['text_values'] = np.asarray(text_values, dtype=np.float32)
    res['text_shape'] = np.asarray(text_shape, dtype=np.int64)
    return res



def load_data_cache(filename):
    with open(filename, "rb") as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break


def pre_build_data_cache(infile, textfile, outfile, feature_cnt, continuous_cnt, text_cnt, batch_size):
    wt = open(outfile, 'wb')
    for labels, features in load_data_from_file_batching(infile, textfile, batch_size, text_cnt):
        input_in_sp = prepare_data_4_sp(labels, features, feature_cnt, continuous_cnt, text_cnt)
        pickle.dump(input_in_sp, wt)
    wt.close()


def single_run(feature_cnt, field_cnt, continuous_cnt, text_cnt, params):

    tf.reset_default_graph()

    print(params)

    extension_name = '_with_text.pkl'
    # extension_name = '.pkl'
    pre_build_data_cache_if_need(params['train_file'], params['train_text_file'], feature_cnt, continuous_cnt, text_cnt, params['batch_size'], extension_name)
    pre_build_data_cache_if_need(params['test_file'], params['test_text_file'], feature_cnt, continuous_cnt, text_cnt, params['batch_size'], extension_name)
    
    params['train_file'] = (params['train_file']).replace('.csv', extension_name).replace('.txt', extension_name).replace('.libfm', extension_name)
    params['test_file'] = (params['test_file']).replace('.csv', extension_name).replace('.txt', extension_name).replace('.libfm', extension_name)
  
    print('start single_run')

    n_epoch = params['n_epoch']
    batch_size = params['batch_size']

    _indices = tf.placeholder(tf.int64, shape=[None, 2], name='raw_indices')
    _values = tf.placeholder(tf.float32, shape=[None], name='raw_values')
    _values2 = tf.placeholder(tf.float32, shape=[None], name='raw_values_square')
    _cont_values = tf.placeholder(tf.float32, shape=[None], name='raw_continuous_values')
    _shape = tf.placeholder(tf.int64, shape=[2], name='raw_shape')  # shape: [instance_cnt, feature_cnt]
    _cont_shape = tf.placeholder(tf.int64, shape=[2], name='raw_continuous_shape')
    _text_values = tf.placeholder(tf.float32, shape=[None], name='raw_text_values')
    _text_shape = tf.placeholder(tf.int64, shape=[2], name='raw_text_shape')

    _y = tf.placeholder(tf.float32, shape=[None, 1], name='Y')
    _ind = tf.placeholder(tf.int64, shape=[None])

    train_step, loss, error, preds, merged_summary, tmp = build_model(_indices, _values, _values2, _cont_values,
                                                                      _text_values,
                                                                      _shape, _cont_shape, _text_shape,  _y, _ind,
                                                                      feature_cnt, field_cnt,
                                                                      continuous_cnt, text_cnt, params)
    saver = tf.train.Saver()
    sess = tf.Session()
    init = tf.global_variables_initializer()
    sess.run(init)

    # log_writer = tf.summary.FileWriter(params['log_path'], graph=sess.graph)

    glo_ite = 0

    tag = params['tag']
    #saver.restore(sess, 'models/[500, 100]0.001-36')
    log_file = open(params['model_path'] + "/result", "a")
    log_file.write(str(datetime.now())+'\n')
    log_file.write(str(params['train_file'])+'\n')
    log_file.write(tag + '\n')
    log_file.close()

    for eopch in range(n_epoch):
        iteration = -1
        start = clock()

        time_load_data, time_sess = 0, 0
        time_cp02 = clock()
        
        train_loss_per_epoch = 0
       
        for training_input_in_sp in load_data_cache(params['train_file']):            
            time_cp01 = clock()
            time_load_data += time_cp01 - time_cp02
            iteration += 1
            glo_ite += 1
            _,  cur_loss, summary, _tmp = sess.run([train_step, loss, merged_summary, tmp], feed_dict={
                _indices: training_input_in_sp['indices'], _values: training_input_in_sp['values'],
                _shape: training_input_in_sp['shape'], _cont_shape: training_input_in_sp['cont_shape'],
                _text_shape: training_input_in_sp['text_shape'], _text_values: training_input_in_sp['text_values'],
                _y: training_input_in_sp['labels'], _values2: training_input_in_sp['values2'],
                _cont_values: training_input_in_sp['cont_values'],
                _ind: training_input_in_sp['feature_indices']
            })

            time_cp02 = clock()

            time_sess += time_cp02 - time_cp01

            train_loss_per_epoch += cur_loss

            # log_writer.add_summary(summary, glo_ite)

        end = clock()

        if eopch % 1 == 0 or eopch == n_epoch-1:
            model_path = params['model_path'] + "/" + str(params['layer_sizes']).replace(':', '_') + str(
                params['reg_w_linear']).replace(':', '_')
            print(model_path)

            os.makedirs(model_path, exist_ok=True)
            # saver.save(sess, model_path, global_step=eopch)

            auc, logloss = predict_test_file(preds, sess, params['test_file'], feature_cnt, _indices, _values, _values2,
                                             _cont_values, _text_values, _shape, _cont_shape, _text_shape, _y, _ind, eopch,
                                             batch_size, tag,
                                             model_path, params['output_predictions'])
            rcd = 'auc is ', auc, 'logloss is ', logloss, ' at epoch  ', eopch, ', time is {0:.4f} min'.format((end - start) / 60.0), ', train_loss is {0:.2f}'.format(train_loss_per_epoch)
            print(rcd)
            log_file = open(params['model_path'] + "/result", "a")
            log_file.write(str(rcd) + '\n')
            log_file.close()
    log_file = open(params['model_path'] + "/result", "a")
    log_file.write('\n\n\n')
    log_file.close()
    # log_writer.close()


def predict_test_file(preds, sess, test_file, feature_cnt, _indices, _values, _values2, _cont_values, _text_values, _shape,
                      _cont_shape, _text_shape, _y, _ind, epoch, batch_size, tag, path, output_prediction=True):
    day = date.today()
    if output_prediction:
        wt = open(path + '/'+str(day)+'_deepFM_pred_' + tag + str(epoch) + '.txt', 'w')

    gt_scores = []
    pred_scores = []

    for test_input_in_sp in load_data_cache(test_file):
        predictios = sess.run(preds, feed_dict={
            _indices: test_input_in_sp['indices'], _values: test_input_in_sp['values'],
            _shape: test_input_in_sp['shape'], _cont_shape: test_input_in_sp['cont_shape'],
            _text_values: test_input_in_sp['text_values'], _text_shape: test_input_in_sp['text_shape'],

            _y: test_input_in_sp['labels'], _values2: test_input_in_sp['values2'],
            _cont_values: test_input_in_sp['cont_values'], _ind: test_input_in_sp['feature_indices']
        }).reshape(-1).tolist()
        
        if output_prediction:
            for (gt, preded) in zip(test_input_in_sp['labels'].reshape(-1).tolist(), predictios):
                wt.write('{0:d},{1:f}\n'.format(int(gt), preded))
                gt_scores.append(gt)
                # pred_scores.append(1.0 if preded >= 0.5 else 0.0)
                pred_scores.append(preded)
        else:
            gt_scores.extend(test_input_in_sp['labels'].reshape(-1).tolist())
            pred_scores.extend(predictios)
    auc = metrics.roc_auc_score(np.asarray(gt_scores), np.asarray(pred_scores))
    logloss = metrics.log_loss(np.asarray(gt_scores), np.asarray(pred_scores))
    # print('auc is ', auc, ', at epoch  ', epoch)
    if output_prediction:
        wt.close()
    return auc, logloss


def build_model(_indices, _values, _values2, _cont_values, _text_values, _shape, _cont_shape, _text_shape, _y, _ind,
                feature_cnt, field_cnt, continuous_cnt, text_cnt, params):
    eta = tf.constant(params['eta'])
    _x = tf.SparseTensor(_indices, _values, _shape)  # m * feature_cnt sparse tensor
    _xx = tf.SparseTensor(_indices, _values2, _shape)
    if params['is_use_continuous_part']:
        _cont_x = tf.reshape(_cont_values, [-1, continuous_cnt])

    if params['is_use_text_part']:
        _text_x = tf.reshape(_text_values, [-1, text_cnt])


    model_params = []
    tmp = []

    init_value = params['init_value']
    dim = params['dim']     # k in fm
    layer_sizes = params['layer_sizes']
    continuous_layer_sizes = params['continuous_layer_sizes']
    text_layer_sizes = params['text_layer_sizes']

    # feature_cnt is total dimension of all features, features can be grouped into fields

    w_linear = tf.Variable(tf.truncated_normal([feature_cnt, 1], stddev=init_value, mean=0),  #tf.random_uniform([feature_cnt, 1], minval=-0.05, maxval=0.05), 
                        name='w_linear', dtype=tf.float32)

    bias = tf.Variable(tf.truncated_normal([1], stddev=init_value, mean=0), name='bias')
    model_params.append(bias)
    model_params.append(w_linear)
    preds = bias
    # linear part
    preds += tf.sparse_tensor_dense_matmul(_x, w_linear, name='contr_from_linear')

    # dense embedding of features
    w_fm = tf.Variable(tf.truncated_normal([feature_cnt, dim], stddev=init_value / math.sqrt(float(10)), mean=0),
                           name='w_fm', dtype=tf.float32)
    model_params.append(w_fm)
    # fm order 2 interactions
    if params['is_use_fm_part']:  
        preds = preds + 0.5 * tf.reduce_sum(
            tf.pow(tf.sparse_tensor_dense_matmul(_x, w_fm), 2) - tf.sparse_tensor_dense_matmul(_xx, tf.pow(w_fm, 2)), 1,
            keep_dims=True)

    # deep neural network
    # filed_cnt indicates the number of valid connections to the first hidden layer.
    # We don't need to specify which field each feature belongs to.
    if params['is_use_dnn_part']:
        w_fm_nn_input = tf.reshape(tf.gather(w_fm, _ind) * tf.expand_dims(_values, 1), [-1, field_cnt * dim])

        # w_nn_layers = []
        hidden_nn_layers = []
        hidden_nn_layers.append(w_fm_nn_input)
        last_layer_size = field_cnt * dim
        layer_idx = 0

        w_nn_params = []
        b_nn_params = []

        for layer_size in layer_sizes:
            '''Caution: initialization of w'''

            cur_w_nn_layer = tf.Variable(
                tf.truncated_normal([last_layer_size, layer_size], stddev=init_value / math.sqrt(float(10)), mean=0),
                name='w_nn_layer' + str(layer_idx), dtype=tf.float32)

            cur_b_nn_layer = tf.Variable(tf.truncated_normal([layer_size], stddev=init_value, mean=0), name='b_nn_layer' + str(layer_idx)) #tf.get_variable('b_nn_layer' + str(layer_idx), [layer_size], initializer=tf.constant_initializer(0.0)) 

            cur_hidden_nn_layer = tf.nn.xw_plus_b(hidden_nn_layers[layer_idx], cur_w_nn_layer, cur_b_nn_layer)
            
            if params['activations'][layer_idx] == 'tanh':
                cur_hidden_nn_layer = tf.nn.tanh(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'sigmoid':
                cur_hidden_nn_layer = tf.nn.sigmoid(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'relu':
                cur_hidden_nn_layer = tf.nn.relu(cur_hidden_nn_layer)
            
            # cur_hidden_nn_layer = tf.matmul(hidden_nn_layers[layer_idx], cur_w_nn_layer)
            # w_nn_layers.append(cur_w_nn_layer)
            hidden_nn_layers.append(cur_hidden_nn_layer)

            layer_idx += 1
            last_layer_size = layer_size

            model_params.append(cur_w_nn_layer)
            model_params.append(cur_b_nn_layer)
            w_nn_params.append(cur_w_nn_layer)
            b_nn_params.append(cur_b_nn_layer)

        w_nn_output = tf.Variable(tf.truncated_normal([last_layer_size, 1], stddev=init_value, mean=0), name='w_nn_output',
                                  dtype=tf.float32)
        nn_output = tf.matmul(hidden_nn_layers[-1], w_nn_output)
        model_params.append(w_nn_output)
        w_nn_params.append(w_nn_output)
        preds += nn_output

    if params['is_use_continuous_part']:
        cont_hidden_nn_layers = []
        cont_hidden_nn_layers.append(_cont_x)
        last_layer_size = continuous_cnt

        cont_w_nn_params = []
        cont_b_nn_params = []

        layer_idx = 0
        for layer_size in continuous_layer_sizes:
            cur_w_nn_layer = tf.Variable(
                tf.truncated_normal([last_layer_size, layer_size], stddev=init_value / math.sqrt(float(last_layer_size)), mean=0),
                name='w_nn_layer' + str(layer_idx), dtype=tf.float32)
            cur_b_nn_layer = tf.Variable(tf.truncated_normal([layer_size], stddev=init_value, mean=0),
                                         name='b_nn_layer' + str(layer_idx))

            cur_hidden_nn_layer = tf.nn.xw_plus_b(cont_hidden_nn_layers[layer_idx], cur_w_nn_layer, cur_b_nn_layer)

            if params['activations'][layer_idx] == 'tanh':
                cur_hidden_nn_layer = tf.nn.tanh(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'sigmoid':
                cur_hidden_nn_layer = tf.nn.sigmoid(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'relu':
                cur_hidden_nn_layer = tf.nn.relu(cur_hidden_nn_layer)

            cont_hidden_nn_layers.append(cur_hidden_nn_layer)

            layer_idx += 1
            last_layer_size = layer_size

            model_params.append(cur_w_nn_layer)
            model_params.append(cur_b_nn_layer)
            cont_w_nn_params.append(cur_w_nn_layer)
            cont_b_nn_params.append(cur_b_nn_layer)

        cont_w_nn_output = tf.Variable(tf.truncated_normal([last_layer_size, 1], stddev=init_value, mean=0),
                                  name='cont_w_nn_output',
                                  dtype=tf.float32)
        cont_nn_output = tf.matmul(cont_hidden_nn_layers[-1], cont_w_nn_output)
        model_params.append(cont_w_nn_output)
        cont_w_nn_params.append(cont_w_nn_output)
        preds += cont_nn_output

    if params['is_use_text_part']:
        text_hidden_nn_layers = []
        text_hidden_nn_layers.append(_text_x)
        last_layer_size = text_cnt

        text_w_nn_params = []
        text_b_nn_params = []

        layer_idx = 0
        for layer_size in text_layer_sizes:
            cur_w_nn_layer = tf.Variable(
                tf.truncated_normal([last_layer_size, layer_size], stddev=init_value / math.sqrt(float(last_layer_size)), mean=0),
                name='w_nn_layer' + str(layer_idx), dtype=tf.float32)
            cur_b_nn_layer = tf.Variable(tf.truncated_normal([layer_size], stddev=init_value, mean=0),
                                         name='b_nn_layer' + str(layer_idx))

            cur_hidden_nn_layer = tf.nn.xw_plus_b(text_hidden_nn_layers[layer_idx], cur_w_nn_layer, cur_b_nn_layer)

            if params['activations'][layer_idx] == 'tanh':
                cur_hidden_nn_layer = tf.nn.tanh(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'sigmoid':
                cur_hidden_nn_layer = tf.nn.sigmoid(cur_hidden_nn_layer)
            elif params['activations'][layer_idx] == 'relu':
                cur_hidden_nn_layer = tf.nn.relu(cur_hidden_nn_layer)

            text_hidden_nn_layers.append(cur_hidden_nn_layer)

            layer_idx += 1
            last_layer_size = layer_size

            model_params.append(cur_w_nn_layer)
            model_params.append(cur_b_nn_layer)
            text_w_nn_params.append(cur_w_nn_layer)
            text_b_nn_params.append(cur_b_nn_layer)

        text_w_nn_output = tf.Variable(tf.truncated_normal([last_layer_size, 1], stddev=init_value, mean=0),
                                  name='text_w_nn_output',
                                  dtype=tf.float32)
        text_nn_output = tf.matmul(text_hidden_nn_layers[-1], text_w_nn_output)
        model_params.append(text_w_nn_output)
        text_w_nn_params.append(text_w_nn_output)
        preds += text_nn_output

    if params['loss'] == 'cross_entropy_loss': # 'loss': 'log_loss'
        error = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=tf.reshape(preds,[-1])
                                                                       , labels=tf.reshape(_y,[-1])))
    elif params['loss'] == 'square_loss':
        preds = tf.sigmoid(preds)
        error = tf.reduce_mean(tf.squared_difference(preds, _y))  
    elif params['loss'] == 'log_loss':
        preds = tf.sigmoid(preds)
        error = tf.reduce_mean(tf.losses.log_loss(predictions=preds, labels=_y))

    lambda_w_linear = tf.constant(params['reg_w_linear'], name='lambda_w_linear')
    lambda_w_fm = tf.constant(params['reg_w_fm'], name='lambda_w_fm')
    lambda_w_nn = tf.constant(params['reg_w_nn'], name='lambda_nn_fm')
    lambda_w_l1 = tf.constant(params['reg_w_l1'], name='lambda_w_l1')

    # l2_norm = tf.multiply(lambda_w_linear, tf.pow(bias, 2)) + tf.reduce_sum(
    #     tf.add(tf.multiply(lambda_w_linear, tf.pow(w_linear, 2)),
    #            tf.multiply(lambda_w_fm, tf.pow(w_fm, 2)))) + tf.reduce_sum(
    #     tf.multiply(lambda_w_nn, tf.pow(w_nn_output, 2)))

    # l2_norm = tf.multiply(lambda_w_linear, tf.pow(bias, 2)) \
    #           + tf.multiply(lambda_w_linear, tf.reduce_sum(tf.pow(w_linear, 2)))

    l2_norm = tf.multiply(lambda_w_linear, tf.reduce_sum(tf.pow(w_linear, 2))) 
    l2_norm += tf.multiply(lambda_w_l1, tf.reduce_sum(tf.abs(w_linear)))

    if params['is_use_fm_part'] or params['is_use_dnn_part']:
        l2_norm += tf.multiply(lambda_w_fm, tf.reduce_sum(tf.pow(w_fm, 2)))

    if params['is_use_dnn_part']:
        for i in range(len(w_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(w_nn_params[i], 2)))
        for i in range(len(b_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(b_nn_params[i], 2)))

    if params['is_use_continuous_part']:
        for i in range(len(cont_w_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(cont_w_nn_params[i], 2)))
        for i in range(len(cont_b_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(cont_b_nn_params[i], 2)))

    if params['is_use_text_part']:
        for i in range(len(text_w_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(text_w_nn_params[i], 2)))
        for i in range(len(text_b_nn_params)):
            l2_norm += tf.multiply(lambda_w_nn, tf.reduce_sum(tf.pow(text_b_nn_params[i], 2)))

    loss = tf.add(error, l2_norm)
    if params['optimizer']=='adadelta':	
        train_step = tf.train.AdadeltaOptimizer(eta).minimize(loss, var_list=model_params)
    elif params['optimizer']=='sgd':
        train_step = tf.train.GradientDescentOptimizer(params['learning_rate']).minimize(loss, var_list=model_params)
    elif params['optimizer']=='adam':
        train_step = tf.train.AdamOptimizer(params['learning_rate']).minimize(loss, var_list=model_params)
    elif params['optimizer']=='ftrl':
        train_step = tf.train.FtrlOptimizer(params['learning_rate']).minimize(loss, var_list=model_params)
    else:
        train_step = tf.train.GradientDescentOptimizer(params['learning_rate']).minimize(loss, var_list=model_params)

    tf.summary.scalar('square_error', error)
    tf.summary.scalar('loss', loss)
    tf.summary.histogram('linear_weights_hist', w_linear)

    if params['is_use_fm_part']:
        tf.summary.histogram('fm_weights_hist', w_fm)
    if params['is_use_dnn_part']:
        for idx in range(len(w_nn_params)):
            tf.summary.histogram('nn_layer'+str(idx)+'_weights', w_nn_params[idx])
    if params['is_use_continuous_part']:
        for idx in range(len(cont_w_nn_params)):
            tf.summary.histogram('cont_nn_layer'+str(idx)+'_weights', cont_w_nn_params[idx])
    if params['is_use_text_part']:
        for idx in range(len(text_w_nn_params)):
            tf.summary.histogram('text_nn_layer'+str(idx)+'_weights', text_w_nn_params[idx])

    merged_summary = tf.summary.merge_all()
    return train_step, loss, error, preds, merged_summary, tmp


# cache data file with pickle format
def pre_build_data_cache_if_need(infile, textfile, feature_cnt, continuous_cont, text_cnt, batch_size, extension_name):
    outfile = infile.replace('.csv', extension_name).replace('.txt', extension_name).replace('.libfm', extension_name)
    if not os.path.isfile(outfile):
        print('pre_build_data_cache for ', infile)
        pre_build_data_cache(infile, textfile, outfile, feature_cnt, continuous_cont, text_cnt, batch_size)
        print('pre_build_data_cache finished.')


def run():

    print('begin running')

    field_cnt = 20  # number of fields(features) 17
    feature_cnt = 37408    # number of dimensions 46207
    continuous_cnt = 10  # dimensions of continuous features
    text_cnt = 200  # dimension of text embedding

    # field_cnt = 18  # number of fields(features) 17
    # feature_cnt = 45617 # number of dimensions 46207

    dir_local = 'E:/Exchange/computing_ad/data/kdd cup 2012 track2/sample/features/mini/'
    dir_remote = '/media/chg/dwt/'

    # train_file = dir_local + 'mini_train.libfm'
    # test_file = dir_local + 'mini_test.libfm'

    train_file = dir_remote + 'kdd/train.nn_no-cl-im-user-comb.libfm'
    test_file = dir_remote + 'kdd/test.nn_no-cl-im-user-comb.libfm'
    train_text_file = dir_remote + 'kdd/trainVector'
    test_text_file = dir_remote + 'kdd/testVector'

    params = {
        'reg_w_linear': 0.0001, 'reg_w_fm':0.0001, 'reg_w_nn': 0.0001,  #0.001
        'reg_w_l1': 0.0001,
        'init_value': 0.1,
        'layer_sizes': [10, 5],
        # 'layer_sizes': [25, 10, 5],
        'continuous_layer_sizes': [6, 3],
        'text_layer_sizes': [10, 5],
        'activations': ['relu','relu','relu'], # tanh, tanh
        'eta': 0.1,
        'n_epoch': 50,  # 500
        'batch_size': 100,
        'dim': 8,
        'model_path': 'models',
        'log_path': 'logs/' + datetime.utcnow().strftime('%Y-%m-%d_%H_%M_%S'),
        'train_file':  train_file,
        'test_file':    test_file,
        'train_text_file': train_text_file,
        'test_text_file': test_text_file,
        'output_predictions': True,
        'is_use_fm_part': True,
        'is_use_dnn_part': True,
        'is_use_continuous_part': False,
        'is_use_text_part': False,
        'learning_rate': 0.01, # [0.001, 0.01]
        'loss': 'log_loss', # [cross_entropy_loss, square_loss, log_loss]
        'optimizer': 'sgd', # [adam, ftrl, sgd]
        'tag': 'original 10-5 0.01_'
    }
    # log_file = open(params['model_path'] + '/result', "a")
    # log_file.write("aa")
    # log_file.close()
    single_run(feature_cnt, field_cnt, continuous_cnt, text_cnt, params)

    # params['tag'] = 'continuous 15-8 0.01_'
    # params['is_use_continuous_part'] = True
    # single_run(feature_cnt, field_cnt, continuous_cnt, params)

    # for cache in load_data_cache(dir_remote+'kdd/train.nn_no-cl-im-user-comb_with_text.pkl'):
    #     print(cache['values'][:10])
    #     print(cache['indices'][:10])
    #     break
    # for cache in load_data_cache(dir_remote+'kdd/train.nn_no-cl-im-user-comb.pkl'):
    #     print(cache['values'][:10])
    #     print(cache['indices'][:10])
    #     break


if __name__ == '__main__':
    print (datetime.now())
    run()
