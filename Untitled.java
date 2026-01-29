import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
import os

# 1. 스타일 설정을 먼저 해야 합니다 (여기서 폰트가 초기화됨)
warnings.filterwarnings('ignore')
sns.set_style('whitegrid')

# 2. 그 다음에 한글 폰트를 설정해야 스타일 설정에 덮어씌워지지 않습니다.
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 12