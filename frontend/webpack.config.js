const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const { ModuleFederationPlugin } = require("webpack").container;
const deps = require("./package.json").dependencies;

module.exports = (_env, argv) => {
  const dev = argv.mode !== "production";
  return {
    entry: "./src/index.ts",
    devtool: dev ? "eval-source-map" : "source-map",
    output: {
      path: path.resolve(__dirname, "dist"),
      // Chunks load from whichever datacenter served remoteEntry.js.
      publicPath: "auto",
      // Content hashes: during a rolling deploy a page never mixes old and new files.
      filename: "[name].[contenthash].js",
      chunkFilename: "[name].[contenthash].js",
      uniqueName: "bcWorkflows",
      clean: true,
    },
    resolve: { extensions: [".tsx", ".ts", ".js"] },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          exclude: /node_modules|\.test\.tsx?$/,
          use: { loader: "ts-loader", options: { transpileOnly: true } },
        },
        {
          test: /\.module\.css$/,
          use: [
            "style-loader",
            {
              loader: "css-loader",
              // Scoped, prefixed class names: nothing leaks into the parent application.
              options: {
                modules: {
                  localIdentName: "bcw-[local]-[hash:base64:6]",
                  namedExport: false,
                  exportLocalsConvention: "as-is",
                },
              },
            },
          ],
        },
      ],
    },
    plugins: [
      new ModuleFederationPlugin({
        name: "bcWorkflows",
        // Not hashed: the parent loads it by a fixed URL. Serve it with Cache-Control: no-cache.
        filename: "remoteEntry.js",
        exposes: {
          "./BcWorkflows": "./src/BcWorkflows.tsx",
          "./mount": "./src/mount.tsx",
        },
        shared: {
          react: { singleton: true, requiredVersion: deps.react },
          "react-dom": { singleton: true, requiredVersion: deps["react-dom"] },
        },
      }),
      // The standalone harness page that stands in for the parent container.
      new HtmlWebpackPlugin({ template: "./public/index.html", title: "BC Workflows (standalone)" }),
      new CopyWebpackPlugin({ patterns: [{ from: "public/config.json" }] }),
    ],
    devServer: {
      port: 3000,
      host: "127.0.0.1",
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache",
      },
    },
  };
};
