import { mount } from "svelte";
import "github-markdown-css/github-markdown-light.css";
import "./style.css";
import App from "./App.svelte";

mount(App, { target: document.getElementById("app") });
