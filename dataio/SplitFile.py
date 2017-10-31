

dir = 'E:/Exchange/computing_ad/data/kdd cup 2012 track2/sample/features/'
train_file = dir + 'train.nn_no-cl-im-user-comb.libfm'
test_file = dir + 'test.nn_no-cl-im-user-comb.libfm'

des_train = open(dir + '/mini/mini_train.libfm', 'w')
des_test = open(dir + '/mini/mini_test.libfm', 'w')

cnt = 0
src = open(test_file, 'r')
for line in src:
    if cnt < 50000:
        des_train.write(line)
    elif cnt > 60000:
        break
    else:
        des_test.write(line)
    cnt += 1

src.close()
des_train.close()
des_test.close()