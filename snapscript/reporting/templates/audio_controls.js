// Переменная для хранения текущего воспроизводимого аудио
let currentlyPlaying = null;
// Переменная для хранения текущей активной кнопки
let currentButton = null;
// Переменная для хранения текущего активного элемента (контейнер транскрипции)
let currentElement = null;
// Массив всех аудио-элементов
let allAudioElements = [];
// Текущая скорость воспроизведения
let currentPlaybackRate = 1.0;
// Следовать ли за аудио
let autoScroll = true;

// Функция инициализации - вызывается при загрузке страницы
window.onload = function() {
    // Собираем все аудио-элементы в массив
    allAudioElements = Array.from(document.querySelectorAll('audio'));
    console.log(`Найдено ${allAudioElements.length} аудио-элементов`);
    
    // Выделяем кнопку скорости 1x как активную по умолчанию
    document.getElementById('speed-1').classList.add('speed-active');
    
    // Устанавливаем начальное значение чекбокса автопрокрутки
    document.getElementById('auto-scroll').checked = autoScroll;
};

// Функция переключения автопрокрутки
function toggleAutoScroll() {
    autoScroll = document.getElementById('auto-scroll').checked;
}

// Функция для изменения скорости воспроизведения
function changeSpeed(speed) {
    // Обновляем текущую скорость
    currentPlaybackRate = speed;
    
    // Применяем скорость к текущему воспроизводимому аудио, если оно есть
    if (currentlyPlaying) {
        currentlyPlaying.playbackRate = speed;
    }
    
    // Обновляем визуальное отображение активной кнопки скорости
    document.querySelectorAll('.speed-button').forEach(button => {
        button.classList.remove('speed-active');
    });
    document.getElementById('speed-' + speed.toString().replace('.', '_')).classList.add('speed-active');
}

// Функция для получения следующего аудио-элемента
function getNextAudio(currentAudio) {
    // Находим индекс текущего аудио в массиве
    const currentIndex = allAudioElements.indexOf(currentAudio);
    // Если текущий элемент найден и это не последний элемент
    if (currentIndex !== -1 && currentIndex < allAudioElements.length - 1) {
        // Возвращаем следующий элемент
        return allAudioElements[currentIndex + 1];
    }
    // В противном случае возвращаем null
    return null;
}

// Функция для прокрутки к элементу
function scrollToElement(element) {
    if (element) {
        // Находим ближайший скриншот до этого элемента
        let prevSnapshot = element.previousElementSibling;
        while (prevSnapshot && !prevSnapshot.classList.contains('snapshot')) {
            prevSnapshot = prevSnapshot.previousElementSibling;
        }
        
        // Если есть скриншот перед текущим элементом и он находится не слишком далеко,
        // прокручиваем к этому скриншоту
        if (prevSnapshot && prevSnapshot.classList.contains('snapshot') && 
            element.offsetTop - prevSnapshot.offsetTop < window.innerHeight) {
            prevSnapshot.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        // Иначе прокручиваем к текущему элементу
        else {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

// Функция для воспроизведения аудио и остановки предыдущего
function playAudio(audioId, buttonElement) {
    // Получаем элемент аудио
    const audioElement = document.getElementById(audioId);
    // Находим контейнер transcript, который содержит этот аудио
    const transcriptElement = buttonElement.closest('.transcript');
    
    // Если есть текущая активная кнопка, убираем класс playing
    if (currentButton) {
        currentButton.classList.remove('playing');
        currentButton.innerHTML = '▶';
    }
    
    // Если есть текущий активный элемент, убираем класс current-playing
    if (currentElement) {
        currentElement.classList.remove('current-playing');
    }
    
    // Если есть текущее воспроизводимое аудио и это не то же самое, что мы пытаемся запустить
    if (currentlyPlaying && currentlyPlaying !== audioElement) {
        // Останавливаем предыдущее аудио
        currentlyPlaying.pause();
        currentlyPlaying.currentTime = 0;
    }
    
    // Если мы нажимаем на уже играющее аудио, останавливаем его
    if (currentlyPlaying === audioElement && !audioElement.paused) {
        audioElement.pause();
        currentlyPlaying = null;
        currentButton = null;
        currentElement = null;
        return;
    }
    
    // Воспроизводим новое аудио и сохраняем ссылку на него
    audioElement.playbackRate = currentPlaybackRate; // Устанавливаем выбранную скорость
    audioElement.play();
    currentlyPlaying = audioElement;
    
    // Сохраняем ссылку на кнопку и изменяем её внешний вид
    currentButton = buttonElement;
    currentButton.classList.add('playing');
    currentButton.innerHTML = '⏸'; // Меняем иконку на "пауза"
    
    // Сохраняем ссылку на элемент и добавляем класс current-playing
    currentElement = transcriptElement;
    currentElement.classList.add('current-playing');
    
    // Если включена опция автопрокрутки, прокручиваем к текущему элементу
    if (autoScroll) {
        scrollToElement(transcriptElement);
    }
    
    // Добавляем обработчик события окончания аудио
    audioElement.onended = function() {
        // Когда аудио закончилось, возвращаем исходный вид кнопке
        if (currentButton) {
            currentButton.classList.remove('playing');
            currentButton.innerHTML = '▶';
        }
        
        // Убираем выделение с текущего элемента
        if (currentElement) {
            currentElement.classList.remove('current-playing');
        }
        
        // Очищаем ссылку на текущее аудио
        currentlyPlaying = null;
        
        // Находим следующий аудио-элемент
        const nextAudio = getNextAudio(audioElement);
        if (nextAudio) {
            // Находим ID кнопки для следующего аудио
            const nextAudioId = nextAudio.id;
            const nextButtonId = 'btn_' + nextAudioId;
            const nextButton = document.getElementById(nextButtonId);
            
            // Если нашли кнопку, запускаем следующее аудио
            if (nextButton) {
                playAudio(nextAudioId, nextButton);
            }
        }
    };
} 