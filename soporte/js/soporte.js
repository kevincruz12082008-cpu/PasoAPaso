(() => {
  const formulario = document.getElementById("formulario-reporte");
  const salida = document.getElementById("salida-reporte");
  const texto = document.getElementById("texto-reporte");
  const botonCopiar = document.getElementById("boton-copiar");
  const avisoCopiado = document.getElementById("aviso-copiado");

  const valor = (datos, clave, porDefecto) => {
    const dato = (datos.get(clave) || "").trim();
    return dato || porDefecto;
  };

  const armarReporte = () => {
    const datos = new FormData(formulario);
    return [
      "REPORTE DE SOPORTE - PasoAPaso",
      "",
      "Nombre: " + valor(datos, "nombre", "-"),
      "Tipo de problema: " + valor(datos, "tipo", "-"),
      "Versión de Windows: " + valor(datos, "windows", "-"),
      "Modo Instantáneo: " + (datos.get("instantaneo") ? "sí" : "no"),
      "Lo que pedí: " + valor(datos, "orden", "-"),
      "",
      "Qué pasó:",
      valor(datos, "descripcion", "-"),
    ].join("\n");
  };

  const ocultarSalida = () => {
    salida.classList.add("d-none");
    avisoCopiado.classList.add("d-none");
  };

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (!formulario.checkValidity()) {
      formulario.classList.add("was-validated");
      ocultarSalida();
      return;
    }
    texto.value = armarReporte();
    avisoCopiado.classList.add("d-none");
    salida.classList.remove("d-none");
    salida.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  formulario.addEventListener("reset", () => {
    formulario.classList.remove("was-validated");
    ocultarSalida();
  });

  const copiarConSeleccion = () => {
    texto.focus();
    texto.select();
    return document.execCommand("copy");
  };

  botonCopiar.addEventListener("click", async () => {
    let copiado = false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(texto.value);
        copiado = true;
      } catch (error) {
        copiado = false;
      }
    }
    if (!copiado) {
      copiado = copiarConSeleccion();
    }
    avisoCopiado.textContent = copiado ? "¡Copiado!" : "Selecciona el texto y presiona Ctrl + C";
    avisoCopiado.classList.remove("d-none");
  });
})();
