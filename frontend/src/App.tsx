import { RouterProvider } from "react-router-dom";

import { router } from "./routes/router";
import "./app/styles.css";


export default function App() {
  return <RouterProvider router={router} />;
}
