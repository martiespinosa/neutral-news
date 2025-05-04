//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    @State private var date: Date = Date.now
    
    @Namespace private var animationNamespace
    
    var body: some View {
        NavigationStack {
            ScrollView {
                if vm.searchText.isEmpty == false && vm.filteredNews.isEmpty {
                    VStack {
                        Spacer()
                        ContentUnavailableView(
                            "No hay resultados para \"\(vm.searchText)\"",
                            systemImage: "magnifyingglass",
                            description: Text("Prueba con otra búsqueda o vuelve a intentarlo más tarde.")
                        )
                        Spacer()
                    }
                    .frame(minHeight: UIScreen.main.bounds.height - 200)
                } else {
                    LazyVStack {
                        ForEach(vm.filteredNews) { neutralNews in
                            NavigationLink {
                                NeutralNewsView(news: neutralNews, relatedNews: vm.getRelatedNews(from: neutralNews), namespace: animationNamespace)
                                    .navigationTransition(.zoom(sourceID: neutralNews.id, in: animationNamespace))
                            } label: {
                                NewsImageView(news: neutralNews, imageUrl: neutralNews.imageUrl)
                                    .padding(.vertical, 4)
                                    .matchedTransitionSource(id: neutralNews.id, in: animationNamespace)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
                
                if vm.isLoafingNeutralNews {
                    VStack {
                        Spacer()
                        ProgressView()
                            .scaleEffect(2)
                        Spacer()
                    }
                    .frame(minHeight: UIScreen.main.bounds.height - 250)
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .refreshable {
                vm.fetchNeutralNewsFromFirestore()
                vm.fetchNewsFromFirestore()
            }
            .searchable(text: $vm.searchText, prompt: "Buscar")
            .navigationTitle("Hoy")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { filterMenu }
            }
        }
    }
    
    var filterMenu: some View {
        Menu {
            Menu("Medio") {
                ForEach(Media.allCases, id: \.self) { media in
                    Button {
                        vm.filterByMedium(media)
                    } label: {
                        Label {
                            Text(media.pressMedia.name)
                        } icon: {
                            if vm.mediaFilter.contains(media) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                    
                }
            }
            Menu("Categoria") {
                ForEach(Category.allCases, id: \.self) { category in
                    Button {
                        vm.filterByCategory(category)
                    } label: {
                        Label {
                            Label(category.rawValue, systemImage: category.systemImageName)
                        } icon: {
                            if vm.categoryFilter.contains(category) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            }
            
            if vm.isAnyFilterEnabled {
                Section {
                    Button("Limpiar Filtros", role: .destructive) {
                        vm.clearFilters()
                    }
                }
            }
        } label: {
            Label("Filtrar", systemImage: vm.isAnyFilterEnabled ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
        }
    }
}

#Preview {
    HomeView()
}
