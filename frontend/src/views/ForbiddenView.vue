<template>
  <main class="forbidden-page">
    <el-result icon="warning" title="无权访问" sub-title="当前账户没有访问此页面的权限。">
      <template #extra>
        <el-button type="primary" @click="$router.replace('/')">返回工作台</el-button>
      </template>
    </el-result>
  </main>
</template>
